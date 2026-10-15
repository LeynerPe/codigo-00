# Despliegue en AWS

El despliegue es la última etapa del pipeline y solo se ejecuta cuando las ocho compuertas
responden `00` en la rama `main`. Toda la infraestructura está definida como código en
`infra/codigo00-infra.yaml` (AWS CloudFormation) y pasa por la compuerta G8 (cfn-lint + Checkov)
antes de desplegarse. No se crea ningún recurso a mano desde la consola.

## Arquitectura de destino

```
Comercios → AWS WAF → Application Load Balancer (HTTPS, TLS 1.2+) → Amazon ECS Fargate (subred privada)
                                                                         ↑
                                                  Amazon ECR (etiqueta inmutable = SHA del commit)
```

Recursos que crea la plantilla (38 en total):

- **Red**: VPC con subredes públicas y privadas en dos zonas de disponibilidad, puerta de enlace a
  internet, una puerta de enlace NAT, tablas de rutas, grupos de seguridad y registros de flujo
  cifrados en CloudWatch Logs.
- **AWS KMS**: llave con rotación automática para registros, secretos e imágenes.
- **Amazon ECR**: etiquetas inmutables, escaneo al publicar y cifrado con KMS.
- **Amazon ECS Fargate**: una tarea de 0,25 vCPU y 0,5 GB, usuario sin privilegios, sistema de
  archivos de solo lectura, sin IP pública y accesible solo desde el balanceador.
- **Application Load Balancer**: solo HTTPS (política `ELBSecurityPolicy-TLS13-1-2-2021-06`),
  descarta encabezados inválidos y guarda registros de acceso en un bucket de S3 privado.
- **AWS WAF**: reglas administradas `AWSManagedRulesCommonRuleSet`,
  `AWSManagedRulesKnownBadInputsRuleSet` y `AWSManagedRulesSQLiRuleSet`, más un límite de
  solicitudes por IP; con registro en CloudWatch Logs.
- **AWS Secrets Manager**: guarda `CODIGO00_API_KEYS`, que la definición de tarea inyecta al contenedor.
- **Amazon CloudWatch Logs**: registros de la API, del WAF y de la red, con retención de 365 días y
  cifrado con KMS (el PAN nunca se registra completo).

## Preparación (una sola vez)

1. Importar o solicitar en AWS Certificate Manager un certificado para el dominio del balanceador
   y copiar su ARN.
2. Copiar el ARN del rol `LabRole` del laboratorio (AWS Academy no permite crear roles de IAM).
3. En GitHub → *Settings* → *Environments* → `produccion`, configurar:
   - Secretos: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` (en AWS Academy las
     credenciales son temporales y se renuevan en cada sesión del laboratorio).
   - Variables: `AWS_REGION`, `LAB_ROLE_ARN`, `CERTIFICATE_ARN`.
   - Revisores obligatorios, si se quiere una aprobación manual antes de producción.

## Qué hace el job `desplegar`

1. Si la pila `codigo00` no existe, la crea con `DesiredCount=0` y una imagen de marcador de
   posición, para que exista el repositorio de Amazon ECR.
2. Construye la imagen y la publica en Amazon ECR con la etiqueta del SHA del commit.
3. Ejecuta `aws cloudformation deploy` con `ImageUri` = esa imagen y `DesiredCount=1`.

## Limitaciones conocidas

- La API guarda las transacciones en una base SQLite local de la tarea, por lo que los datos no
  persisten si la tarea se reinicia y el servicio no puede escalar a más de una tarea sin una base de
  datos compartida (por ejemplo, Amazon RDS). Por eso `DesiredCount` solo admite 0 o 1.
- La llave de API de los comercios se carga en Secrets Manager después de crear la pila
  (`aws secretsmanager put-secret-value`), para no escribirla en la plantilla.
- Las credenciales del laboratorio expiran al terminar la sesión; conviene volver a cargar los
  secretos de GitHub antes de cada demostración.
