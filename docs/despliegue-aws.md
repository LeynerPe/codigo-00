# Despliegue en AWS

El despliegue es la última etapa del pipeline y solo se ejecuta cuando todas las compuertas
responden `00` en la rama `main`.

## Arquitectura de destino

```
Internet → AWS WAF → Application Load Balancer → Amazon ECS (Fargate) → contenedor codigo00
                                                     ↑
                                         Amazon ECR (imagen firmada por SHA del commit)
```

- **Amazon ECR**: repositorio privado de imágenes, con escaneo de imágenes al publicar.
- **Amazon ECS en Fargate**: ejecuta el contenedor sin administrar servidores.
- **Application Load Balancer**: termina TLS (certificado de ACM) y enruta al servicio.
- **AWS WAF**: reglas administradas `AWSManagedRulesCommonRuleSet` y `AWSManagedRulesSQLiRuleSet`
  delante del ALB, como defensa adicional (tema del módulo 9 del curso).
- **AWS Secrets Manager**: guarda `CODIGO00_API_KEYS` y `CODIGO00_TOKEN_KEY`; la definición de tarea
  los inyecta como variables de entorno.
- **Amazon CloudWatch Logs**: registros del contenedor (el PAN nunca se registra completo).

## Preparación (una sola vez)

1. Crear el repositorio ECR: `aws ecr create-repository --repository-name codigo00 --image-scanning-configuration scanOnPush=true`
2. Crear el clúster y el servicio ECS (Fargate) con la definición de tarea que usa la imagen de ECR,
   el puerto 8000 y el *health check* `/health`.
3. Crear el ALB, el grupo de destino y asociar la ACL web de AWS WAF.
4. En GitHub → *Settings* → *Environments* → `produccion`, configurar:
   - Secretos: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` (en AWS Academy las
     credenciales son temporales y se renuevan en cada sesión del laboratorio).
   - Variables: `AWS_REGION`, `ECR_REPOSITORY`, `ECS_CLUSTER`, `ECS_SERVICE`.
   - Revisores obligatorios, si se quiere una aprobación manual antes de producción.

## Nota sobre AWS Academy

Las cuentas del laboratorio tienen permisos de IAM restringidos (rol `LabRole`) y credenciales que
expiran al terminar la sesión. Por eso el pipeline usa `aws-session-token` y conviene volver a cargar
los secretos antes de cada demostración.
