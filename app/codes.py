"""Códigos de respuesta inspirados en el campo 39 de ISO 8583.

Solo se usa el subconjunto necesario para la API simulada. Las descripciones
siguen la denominación habitual de las redes de pago.
"""

from enum import Enum


class ResponseCode(str, Enum):
    APPROVED = "00"
    DO_NOT_HONOR = "05"
    INVALID_TRANSACTION = "12"
    INVALID_AMOUNT = "13"
    INVALID_CARD_NUMBER = "14"
    UNABLE_TO_LOCATE_RECORD = "25"
    INSUFFICIENT_FUNDS = "51"
    EXPIRED_CARD = "54"
    EXCEEDS_AMOUNT_LIMIT = "61"
    ORIGINAL_AMOUNT_INCORRECT = "64"
    DUPLICATE_TRANSMISSION = "94"
    SYSTEM_MALFUNCTION = "96"


MESSAGES = {
    ResponseCode.APPROVED: "Aprobada",
    ResponseCode.DO_NOT_HONOR: "No aprobada",
    ResponseCode.INVALID_TRANSACTION: "Transacción inválida",
    ResponseCode.INVALID_AMOUNT: "Monto inválido",
    ResponseCode.INVALID_CARD_NUMBER: "Número de tarjeta inválido",
    ResponseCode.UNABLE_TO_LOCATE_RECORD: "Transacción original no encontrada",
    ResponseCode.INSUFFICIENT_FUNDS: "Fondos insuficientes",
    ResponseCode.EXPIRED_CARD: "Tarjeta vencida",
    ResponseCode.EXCEEDS_AMOUNT_LIMIT: "Excede el monto máximo permitido",
    ResponseCode.ORIGINAL_AMOUNT_INCORRECT: "El monto no coincide con la transacción original",
    ResponseCode.DUPLICATE_TRANSMISSION: "Transmisión duplicada",
    ResponseCode.SYSTEM_MALFUNCTION: "Error del sistema",
}


def message_for(code: ResponseCode) -> str:
    return MESSAGES[code]
