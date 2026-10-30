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

## Preparación (en cada sesión de AWS Academy)

1. En AWS Academy, abrir el laboratorio (Learner Lab), pulsar **Start Lab** y luego **AWS Details →
   AWS CLI: Show**.
2. En GitHub → *Settings* → *Environments* → `produccion` (o *Secrets and variables → Actions*), cargar los
   secretos `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_SESSION_TOKEN` con esos valores. Las
   credenciales del laboratorio expiran al terminar la sesión.
3. Opcional: la variable `AWS_REGION` (por defecto `us-east-1`). `LAB_ROLE_ARN` y `CERTIFICATE_ARN` también
   son opcionales: si no existen, el flujo usa el rol `LabRole` de la cuenta y crea un certificado autofirmado
   de laboratorio (`codigo00.lab`) que importa en AWS Certificate Manager.
4. En *Actions*, ejecutar a mano el flujo **Código 00 — pipeline DevSecOps** sobre `main`.

## Qué hace el flujo después de las compuertas

1. **desplegar:** si la pila `codigo00` no existe, la crea con `DesiredCount=0`; reemplaza la llave de API de
   marcador de posición por una llave aleatoria (sin mostrarla); publica la imagen en Amazon ECR con la
   etiqueta del SHA del commit; despliega la plantilla con `DesiredCount=1` y ejecuta pruebas de humo:
   `GET /health` por HTTPS (200), consulta sin llave (401), inyección SQL bloqueada por AWS WAF (403) y
   ausencia de respuesta por HTTP en el puerto 80. Si la pila falla, imprime sus eventos fallidos.
2. **cspm:** ejecuta Prowler sobre la región del despliegue y publica el reporte (HTML, CSV y JSON OCSF) como
   artefacto `cspm-prowler`.

Para no consumir créditos, al terminar se ejecuta a mano el flujo **Código 00 — eliminar despliegue en AWS**,
que vacía el bucket de registros, elimina la pila y borra el certificado de laboratorio.

## Limitaciones conocidas

- La API guarda las transacciones en una base SQLite local de la tarea, por lo que los datos no
  persisten si la tarea se reinicia y el servicio no puede escalar a más de una tarea sin una base de
  datos compartida (por ejemplo, Amazon RDS). Por eso `DesiredCount` solo admite 0 o 1.
- La llave de API de los comercios no se escribe en la plantilla: el flujo la genera y la guarda en Secrets
  Manager en el primer despliegue (`aws secretsmanager put-secret-value`).
- El certificado autofirmado solo sirve para el laboratorio: los clientes deben aceptar el certificado
  (por ejemplo, `curl -k`). En producción se usaría un certificado de ACM validado para un dominio propio.
- Las credenciales del laboratorio expiran al terminar la sesión; conviene volver a cargar los
  secretos de GitHub antes de cada demostración.
