"""先用确定性规则完成回复分流，复杂或低置信度内容再升级模型。"""

from __future__ import annotations

from src.domain.inbound_email import InboundEmail
from src.domain.reply_analysis import ReplyAnalysis, ReplyCategory


def classify_inbound(message: InboundEmail) -> ReplyAnalysis:
    text = f"{message.subject} {message.body}".lower()
    if message.is_bounce:
        return _result(
            message, ReplyCategory.BOUNCE, 0.99, "high",
            "暂停该地址并人工检查退信原因", True, ("bounce signal",)
        )
    rules = (
        (ReplyCategory.COMPLAINT, (
            "complaint", "破损", "投诉", "法律", "refund", "beschwerde",
            "réclamation", "reclamation", "queja", "reclamo", "reclamação",
        ),
         0.94, "high", "暂停自动跟进，转人工处理", True),
        (ReplyCategory.PRICING, (
            "price", "pricing", "quote", "报价", "价格", "preis", "angebot",
            "prix", "devis", "precio", "cotización", "prezzo", "preventivo",
            "preço", "cotação",
        ),
         0.91, "medium", "准备报价和成本信息供人工确认", False),
        (ReplyCategory.DELIVERY, (
            "lead time", "delivery", "shipping", "交期", "交货", "lieferzeit",
            "versand", "délai", "livraison", "plazo de entrega", "envío",
            "tempo di consegna", "spedizione", "prazo de entrega", "envio",
        ),
         0.91, "medium", "准备交期和物流信息供人工确认", False),
        (ReplyCategory.NOT_INTERESTED, (
            "not interested", "no thanks", "不要", "不感兴趣", "kein interesse",
            "pas intéressé", "no me interesa", "non interessato", "não interessado",
        ),
         0.93, "low", "停止当前跟进并记录拒绝", False),
        (ReplyCategory.INTERESTED, (
            "interested", "catalogue", "catalog", "sample", "感兴趣", "目录", "样品",
            "interessiert", "katalog", "muster", "intéressé", "échantillon",
            "interesado", "catálogo", "muestra", "interessato", "campione",
            "interessado", "amostra",
        ),
         0.88, "low", "创建人工跟进待办", False),
    )
    for category, tokens, confidence, risk, action, review in rules:
        matched = tuple(token for token in tokens if token in text)
        if matched:
            return _result(message, category, confidence, risk, action, review, matched)
    return _result(
        message, ReplyCategory.OTHER, 0.45, "medium",
        "人工阅读原文后决定下一步", True, ()
    )


def _result(message, category, confidence, risk, action, review, evidence):
    return ReplyAnalysis.create(
        message.message_id, message.task_id, message.lead_domain,
        category, confidence, risk, action, review, evidence,
    )
