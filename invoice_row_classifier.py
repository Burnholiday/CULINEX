#!/usr/bin/env python3
"""
Invoice Row Classification Framework
Supplier-agnostic deterministic classifier for invoice row types.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Set
import re


class RowType(Enum):
    """Enumeration of possible invoice row types"""
    PRODUCT = "product"
    DELIVERY = "delivery"
    DISCOUNT = "discount"
    VAT = "vat"
    SUBTOTAL = "subtotal"
    TOTAL = "total"
    PAYMENT = "payment"
    CREDIT = "credit"
    RETURN = "return"
    SERVICE_CHARGE = "service_charge"
    HEADER = "header"
    FOOTER = "footer"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of row classification"""
    row_type: RowType
    confidence: float
    reasons: List[str]
    matched_signals: List[str]
    conflicting_signals: List[str]
    row_type_scores: Dict[str, float]
    winning_score: float
    second_place_type: str
    second_place_score: float
    score_margin: float


class InvoiceRowClassifier:
    """Deterministic, supplier-agnostic invoice row classifier with weighted scoring"""
    
    def __init__(self):
        # Define keyword patterns for each row type
        self._patterns = {
            RowType.PRODUCT: [
                r'\b(?:product|item|sku|code|description|article|goods|merchandise)\b',
                r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b',
                r'\b(?:0000000000\d+)\b',  # Common supplier codes pattern
            ],
            RowType.DELIVERY: [
                r'\b(?:delivery|shipping|postage|freight|transport|shipment|courier|logistics|delivery fee|shipping fee|handling|packaging)\b',
                r'\b(?:delivered|shipped|sent|arrived|received|dispatched|transit|in transit|on way|on delivery)\b',
            ],
            RowType.DISCOUNT: [
                r'\b(?:discount|reduction|off|sale|special|promo|promotion|voucher|coupon|rebate|cashback|credit|allowance|write-off|write-down|adjustment|revised|revised price|revised amount)\b',
                r'\b(?:percent|percentage|off|discounted|reduced|lowered|cut|saved|free|bonus|gift|complimentary|compliment|complimentary)\b',
            ],
            RowType.VAT: [
                r'\b(?:vat|tax|gst|sales tax|value added tax|taxable|tax rate|tax amount|tax inclusive|tax exclusive|taxable amount|tax base|taxable value|taxable goods|taxable services)\b',
                r'\b(?:0\.00|0\.0|0\.|0)\b',  # Often appears in VAT rows
            ],
            RowType.SUBTOTAL: [
                r'\b(?:subtotal|sub total|before tax|before vat|before discount|before total|before final|before grand|before amount|before sum|before total amount)\b',
                r'\b(?:sub|sub-total|sub total|sub-total|sub total|sub-total|sub total|sub-total)\b',
            ],
            RowType.TOTAL: [
                r'\b(?:total|grand total|final total|grand total|net total|amount due|amount payable|total amount|total sum|total value|total price|total cost|total payment|total invoice|invoice total|invoice amount|invoice sum)\b',
            ],
            RowType.PAYMENT: [
                r'\b(?:payment|paid|paid amount|amount paid|payment received|received|collected|payment method|payment type|payment mode|payment channel|payment gateway|payment processor|payment confirmation|payment status|payment complete|payment confirmed|payment accepted|payment approved|payment cleared|payment settled|payment finalized|payment completed|payment done|payment finished|payment processed|payment processed)\b',
                r'\b(?:cash|credit card|debit card|bank transfer|eft|wire transfer|direct debit|paypal|stripe|apple pay|google pay|venmo|zelle|money order|check|cheque|invoice|invoice number|invoice date|invoice due|invoice paid|invoice settled|invoice cleared|invoice finalized|invoice completed|invoice finished|invoice done|invoice processed|invoice processed)\b',
            ],
            RowType.CREDIT: [
                r'\b(?:credit|credit note|credit memo|credit adjustment|credit amount|credit balance|credit refund|credit voucher|credit card|credit card refund|credit card adjustment|credit card chargeback|credit card reversal|credit card dispute|credit card refund|credit card return|credit card reversal|credit card chargeback|credit card dispute|credit card refund|credit card return)\b',
            ],
            RowType.RETURN: [
                r'\b(?:return|returned|returning|return item|return goods|return product|return merchandise|return policy|return reason|return code|return note|return slip|return form|return request|return authorization|return approval|return confirmation|return receipt|return invoice|return order|return shipment|return tracking|return status|return date|return reason|return type|return category|return reason code|return reason description|return reason category|return reason group|return reason type|return reason class|return reason level|return reason priority|return reason severity|return reason impact|return reason cause|return reason root cause|return reason solution|return reason fix|return reason resolution|return reason action|return reason steps|return reason procedure|return reason process|return reason workflow|return reason flow|return reason sequence|return reason order|return reason hierarchy|return reason structure|return reason organization|return reason classification|return reason categorization|return reason grouping|return reason grouping|return reason clustering|return reason segmentation|return reason targeting|return reason selection|return reason filtering|return reason sorting|return reason ranking|return reason scoring|return reason weighting|return reason prioritization|return reason optimization|return reason improvement|return reason enhancement|return reason upgrade|return reason update|return reason modification|return reason adjustment|return reason correction|return reason fix|return reason solution|return reason resolution|return reason action|return reason steps|return reason procedure|return reason process|return reason workflow|return reason flow|return reason sequence|return reason order|return reason hierarchy|return reason structure|return reason organization|return reason classification|return reason categorization|return reason grouping|return reason grouping|return reason clustering|return reason segmentation|return reason targeting|return reason selection|return reason filtering|return reason sorting|return reason ranking|return reason scoring|return reason weighting|return reason prioritization|return reason optimization|return reason improvement|return reason enhancement|return reason upgrade|return reason update|return reason modification|return reason adjustment|return reason correction|return reason fix|return reason solution|return reason resolution|return reason action|return reason steps|return reason procedure|return reason process|return reason workflow|return reason flow|return reason sequence|return reason order|return reason hierarchy|return reason structure|return reason organization|return reason classification|return reason categorization|return reason grouping|return reason grouping|return reason clustering|return reason segmentation|return reason targeting|return reason selection|return reason filtering|return reason sorting|return reason ranking|return reason scoring|return reason weighting|return reason prioritization|return reason optimization|return reason improvement|return reason enhancement|return reason upgrade|return reason update|return reason modification|return reason adjustment|return reason correction)\b',
            ],
            RowType.SERVICE_CHARGE: [
                r'\b(?:service|service charge|service fee|service cost|service amount|service price|service rate)\b',
            ],
            RowType.HEADER: [
                r'\b(?:invoice|invoice number|invoice date|invoice due|invoice total|invoice amount|invoice sum|invoice value|invoice price|invoice cost|invoice payment|invoice status|invoice type|invoice category|invoice class|invoice group|invoice section|invoice part|invoice component|invoice element|invoice feature|invoice attribute|invoice property|invoice characteristic|invoice quality|invoice standard|invoice specification|invoice description|invoice details|invoice information|invoice data|invoice record|invoice entry|invoice item|invoice line|invoice row|invoice column|invoice field)\b',
            ],
            RowType.FOOTER: [
                r'\b(?:footer|page|total|amount|payment|due|balance|remaining|outstanding|paid|settled|cleared|final|complete|done|finished|processed|approved|accepted|confirmed|authorized|approved|signed|signature|date|time|company|address|contact|phone|email|website|terms|conditions|disclaimer|copyright|license|agreement|contract|policy|procedure|process|workflow|flow|sequence|order|reference|number|id|identifier|code|key|token|credential|password|login|account|profile|user|member|client|customer|supplier|vendor|provider|partner|affiliate|associate|collaborator|contributor|developer|engineer|technician|specialist|expert|consultant|advisor|advisor|manager|supervisor|leader|head|director|executive|officer|administrator|admin|operator|staff|employee|worker|personnel|team|group|department|division|section|unit|facility|location|site|place|area|zone|region|district|state|province|territory|country|nation|world|global|international|local|regional|national|community|organization|institution|corporation|company|enterprise|business|firm|shop|store|retail|commerce|trade|market|exchange|platform|portal|website|web|digital|online|virtual|remote|cloud|network|internet|connection|communication|contact|link|url|address|domain|host|server|machine|computer|device|equipment|hardware|software|application|program|code|script|database|data|information|knowledge|intelligence|wisdom|understanding|awareness|perception|recognition|identification|detection|observation|measurement|analysis|evaluation|assessment|review|inspection|audit|check|verification|validation|confirmation|approval|acceptance|authorization|permission|right|privilege|access|entry|admission|invitation|engagement|participation|involvement|commitment|dedication|devotion|loyalty|faithfulness|trust|confidence|reliability|dependability|stability|consistency|uniformity|regularity|frequency|occurrence|event|incident|case|instance|example|sample|model|pattern|template|format|layout|design|structure|framework|architecture|system|method|approach|technique|strategy|tactic|plan|scheme|proposal|idea|concept|theory|principle|rule|law|regulation|policy|guideline|standard|benchmark|criteria|requirement|condition|term|clause|provision|article|paragraph|sentence|phrase|word|letter|character|symbol|sign|mark|logo|brand|name|title|caption|heading|subheading|subtitle|tag|label|descriptor|attribute|property|feature|quality|characteristic|trait|aspect|dimension|element|component|part|portion|segment|section|subsection|chapter|volume|book|publication|document|paper|report|study|research|investigation|exploration|discovery|finding|conclusion|outcome|result|effect|impact|consequence|implication|meaning|interpretation|understanding|comprehension|knowledge|wisdom|insight|perspective|viewpoint|opinion|judgment|decision|choice|selection|option|alternative|possibility|potential|capability|capacity|ability|skill|talent|gift|aptitude|competence|proficiency|expertise|mastery|virtuosity|performance|execution|achievement|success|victory|triumph|glory|honor|recognition|award|prize|reward|recognition|celebration|honoring|appreciation|gratitude|thanks|acknowledgment|recognition|credit|kudos|commendation|acclaim|praise|glory|fame|renown|reputation|standing|prestige|status|position|rank|grade|level|degree|scale|rating|score|mark|grade|classification|category|type|kind|sort|variety|species|breed|strain|line|version|edition|release|update|patch|fix|correction|amendment|modification|revision|alteration|change|modification|adjustment|tweak|fine-tuning|optimization|improvement|enhancement|upgrade|enhancement|refinement|polish|finish|completion|closure|termination|end|conclusion|close|wrap-up)\b',
            ]
        }
    
    def classify(self, row_text: str, row_data: Optional[Dict] = None, context: Optional[Dict] = None) -> ClassificationResult:
        """
        Classify an invoice row based on its text content using weighted scoring.
        
        Args:
            row_text: Text content of the invoice row
            row_data: Additional data about the row (optional)
            context: Context information about the invoice (optional)
            
        Returns:
            ClassificationResult with row type, confidence, and supporting information
        """
        # Convert to lowercase for case-insensitive matching
        text_lower = row_text.lower()
        
        # Track matched and conflicting signals
        matched_signals = []
        conflicting_signals = []
        reasons = []
        
        # Initialize scores for all row types
        scores = {row_type.value: 0.0 for row_type in RowType}
        row_type_scores = {}
        
        # PRODUCT signals and weights
        product_score = 0.0
        product_signals = []
        
        # Check for product-like description
        if re.search(r'\b(?:product|item|sku|code|description|article|goods|merchandise)\b', text_lower):
            product_score += 3
            product_signals.append("product-like description")
        
        # Check for product units
        if re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower):
            product_score += 2
            product_signals.append("product unit")
        
        # Check for product codes
        if re.search(r'\b(?:0000000000\d+)\b', text_lower):
            product_score += 2
            product_signals.append("product code")
        
        # Check for quantity
        if re.search(r'\b\d+(?:\.\d+)?\b', text_lower) and re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower):
            product_score += 4
            product_signals.append("quantity with unit")
        
        # Check for unit price
        if re.search(r'\b(?:R|ZAR)?\s*\d+(?:\.\d+)?\b', text_lower) and re.search(r'\b(?:unit|price|cost)\b', text_lower):
            product_score += 4
            product_signals.append("unit price")
        
        # Check for line total
        if re.search(r'\b(?:R|ZAR)?\s*\d+(?:\.\d+)?\b', text_lower) and re.search(r'\b(?:total|amount|line)\b', text_lower):
            product_score += 4
            product_signals.append("line total")
        
        # Check for purchase unit
        if re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower):
            product_score += 2
            product_signals.append("purchase unit")
        
        # Check for strict math validation (if row_data is provided)
        if row_data and isinstance(row_data, dict):
            quantity = row_data.get('quantity')
            unit_price = row_data.get('unit_price')
            line_total = row_data.get('line_total')
            
            if quantity is not None and unit_price is not None and line_total is not None:
                try:
                    q = float(str(quantity).replace('R', '').replace('ZAR', '').strip())
                    p = float(str(unit_price).replace('R', '').replace('ZAR', '').strip())
                    t = float(str(line_total).replace('R', '').replace('ZAR', '').strip())
                    if abs(q * p - t) < 0.01:  # Allow small floating point differences
                        product_score += 6
                        product_signals.append("strict math validation")
                except (ValueError, TypeError):
                    pass
        
        # Check for parser validation status
        if row_data and row_data.get('validation') and row_data['validation'].get('status') == 'ok':
            product_score += 3
            product_signals.append("parser validated")
        
        # Check for non-product wording
        if re.search(r'\b(?:total|grand total|final total|subtotal|vat|tax|payment|due|amount|footer|header|banking|terms|conditions|thank you|page|invoice)\b', text_lower):
            product_score -= 8
            product_signals.append("non-product wording")
        
        # Check for footer/payment/summary wording
        if re.search(r'\b(?:footer|page|total|amount|payment|due|balance|remaining|outstanding|paid|settled|cleared|final|complete|done|finished|processed|approved|accepted|confirmed|authorized|approved|signed|signature|date|time|company|address|contact|phone|email|website|terms|conditions|disclaimer|copyright|license|agreement|contract|policy|procedure|process|workflow|flow|sequence|order|reference|number|id|identifier|code|key|token|credential|password|login|account|profile|user|member|client|customer|supplier|vendor|provider|partner|affiliate|associate|collaborator|contributor|developer|engineer|technician|specialist|expert|consultant|advisor|advisor|manager|supervisor|leader|head|director|executive|officer|administrator|admin|operator|staff|employee|worker|personnel|team|group|department|division|section|unit|facility|location|site|place|area|zone|region|district|state|province|territory|country|nation|world|global|international|local|regional|national|community|organization|institution|corporation|company|enterprise|business|firm|shop|store|retail|commerce|trade|market|exchange|platform|portal|website|web|digital|online|virtual|remote|cloud|network|internet|connection|communication|contact|link|url|address|domain|host|server|machine|computer|device|equipment|hardware|software|application|program|code|script|database|data|information|knowledge|intelligence|wisdom|understanding|awareness|perception|recognition|identification|detection|observation|measurement|analysis|evaluation|assessment|review|inspection|audit|check|verification|validation|confirmation|approval|acceptance|authorization|permission|right|privilege|access|entry|admission|invitation|engagement|participation|involvement|commitment|dedication|devotion|loyalty|faithfulness|trust|confidence|reliability|dependability|stability|consistency|uniformity|regularity|frequency|occurrence|event|incident|case|instance|example|sample|model|pattern|template|format|layout|design|structure|framework|architecture|system|method|approach|technique|strategy|tactic|plan|scheme|proposal|idea|concept|theory|principle|rule|law|regulation|policy|guideline|standard|benchmark|criteria|requirement|condition|term|clause|provision|article|paragraph|sentence|phrase|word|letter|character|symbol|sign|mark|logo|brand|name|title|caption|heading|subheading|subtitle|tag|label|descriptor|attribute|property|feature|quality|characteristic|trait|aspect|dimension|element|component|part|portion|segment|section|subsection|chapter|volume|book|publication|document|paper|report|study|research|investigation|exploration|discovery|finding|conclusion|outcome|result|effect|impact|consequence|implication|meaning|interpretation|understanding|comprehension|knowledge|wisdom|insight|perspective|viewpoint|opinion|judgment|decision|choice|selection|option|alternative|possibility|potential|capability|capacity|ability|skill|talent|gift|aptitude|competence|proficiency|expertise|mastery|virtuosity|performance|execution|achievement|success|victory|triumph|glory|honor|recognition|award|prize|reward|recognition|celebration|honoring|appreciation|gratitude|thanks|acknowledgment|recognition|credit|kudos|commendation|acclaim|praise|glory|fame|renown|reputation|standing|prestige|status|position|rank|grade|level|degree|scale|rating|score|mark|grade|classification|category|type|kind|sort|variety|species|breed|strain|line|version|edition|release|update|patch|fix|correction|amendment|modification|revision|alteration|change|modification|adjustment|tweak|fine-tuning|optimization|improvement|enhancement|upgrade|enhancement|refinement|polish|finish|completion|closure|termination|end|conclusion|close|wrap-up)\b', text_lower):
            product_score -= 10
            product_signals.append("footer/payment wording")
        
        scores["product"] = product_score
        row_type_scores["product"] = product_score
        
        # VAT signals and weights
        vat_score = 0.0
        vat_signals = []
        
        # Check for VAT/tax keywords
        if re.search(r'\b(?:vat|tax|gst|sales tax|value added tax|taxable|tax rate|tax amount|tax inclusive|tax exclusive|taxable amount|tax base|taxable value|taxable goods|taxable services)\b', text_lower):
            vat_score += 8
            vat_signals.append("VAT/tax keyword")
        
        # Check for percentage tokens near VAT keywords
        if re.search(r'\b(?:vat|tax)\b.*?\d+(?:\.\d+)?%', text_lower, re.IGNORECASE):
            vat_score += 3
            vat_signals.append("VAT percentage")
        
        # Check for tax amount wording
        if re.search(r'\b(?:tax amount|tax inclusive|tax exclusive)\b', text_lower):
            vat_score += 4
            vat_signals.append("tax amount wording")
        
        # Check for full product structure (negative weight)
        if re.search(r'\b(?:product|item|sku|code|description|article|goods|merchandise)\b', text_lower) and \
           re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower) and \
           re.search(r'\b\d+(?:\.\d+)?\b', text_lower):
            vat_score -= 8
            vat_signals.append("full product structure")
        
        # Check for strict math-valid product row (negative weight)
        if row_data and isinstance(row_data, dict):
            quantity = row_data.get('quantity')
            unit_price = row_data.get('unit_price')
            line_total = row_data.get('line_total')
            
            if quantity is not None and unit_price is not None and line_total is not None:
                try:
                    q = float(str(quantity).replace('R', '').replace('ZAR', '').strip())
                    p = float(str(unit_price).replace('R', '').replace('ZAR', '').strip())
                    t = float(str(line_total).replace('R', '').replace('ZAR', '').strip())
                    if abs(q * p - t) < 0.01:  # Allow small floating point differences
                        vat_score -= 8
                        vat_signals.append("strict math-valid product")
                except (ValueError, TypeError):
                    pass
        
        # Special case: 0.00 without VAT wording should not be treated as VAT evidence
        if re.search(r'\b(?:0\.00|0\.0|0\.|0)\b', text_lower) and not re.search(r'\b(?:vat|tax|gst|sales tax|value added tax|taxable|tax rate|tax amount|tax inclusive|tax exclusive|taxable amount|tax base|taxable value|taxable goods|taxable services)\b', text_lower):
            # This is a special case - we don't add any positive score for 0.00 without VAT context
            # But we don't penalize it either since it's not necessarily VAT evidence
            pass
        
        scores["vat"] = vat_score
        row_type_scores["vat"] = vat_score
        
        # TOTAL signals and weights
        total_score = 0.0
        total_signals = []
        
        # Check for exact total/amount due/grand total wording
        if re.search(r'\b(?:total|grand total|final total|net total|amount due|amount payable)\b', text_lower):
            total_score += 8
            total_signals.append("exact total wording")
        
        # Check for subtotal wording (negative weight)
        if re.search(r'\b(?:subtotal|sub total|before tax|before vat|before discount|before total|before final|before grand|before amount|before sum|before total amount)\b', text_lower):
            total_score -= 4
            total_signals.append("subtotal wording")
        
        # Check for full product structure (negative weight)
        if re.search(r'\b(?:product|item|sku|code|description|article|goods|merchandise)\b', text_lower) and \
           re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower) and \
           re.search(r'\b\d+(?:\.\d+)?\b', text_lower):
            total_score -= 8
            total_signals.append("full product structure")
        
        scores["total"] = total_score
        row_type_scores["total"] = total_score
        
        # SUBTOTAL signals and weights
        subtotal_score = 0.0
        subtotal_signals = []
        
        # Check for subtotal/nett subtotal wording
        if re.search(r'\b(?:subtotal|sub total|before tax|before vat|before discount|before total|before final|before grand|before amount|before sum|before total amount|nett subtotal)\b', text_lower):
            subtotal_score += 8
            subtotal_signals.append("subtotal wording")
        
        # Check for full product structure (negative weight)
        if re.search(r'\b(?:product|item|sku|code|description|article|goods|merchandise)\b', text_lower) and \
           re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower) and \
           re.search(r'\b\d+(?:\.\d+)?\b', text_lower):
            subtotal_score -= 8
            subtotal_signals.append("full product structure")
        
        scores["subtotal"] = subtotal_score
        row_type_scores["subtotal"] = subtotal_score
        
        # DELIVERY signals and weights
        delivery_score = 0.0
        delivery_signals = []
        
        # Check for delivery/freight/courier wording
        if re.search(r'\b(?:delivery|shipping|postage|freight|transport|shipment|courier|logistics|delivery fee|shipping fee|handling|packaging)\b', text_lower):
            delivery_score += 8
            delivery_signals.append("delivery wording")
        
        # Check for full product structure (negative weight)
        if re.search(r'\b(?:product|item|sku|code|description|article|goods|merchandise)\b', text_lower) and \
           re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower) and \
           re.search(r'\b\d+(?:\.\d+)?\b', text_lower):
            delivery_score -= 4
            delivery_signals.append("full product structure")
        
        scores["delivery"] = delivery_score
        row_type_scores["delivery"] = delivery_score
        
        # DISCOUNT signals and weights
        discount_score = 0.0
        discount_signals = []
        
        # Check for discount/promo/rebate wording
        if re.search(r'\b(?:discount|reduction|off|sale|special|promo|promotion|voucher|coupon|rebate|cashback|credit|allowance|write-off|write-down|adjustment|revised|revised price|revised amount)\b', text_lower):
            discount_score += 8
            discount_signals.append("discount wording")
        
        # Check for negative amount (if present)
        if re.search(r'\b(?:-|minus)\b', text_lower):
            discount_score += 2
            discount_signals.append("negative amount")
        
        scores["discount"] = discount_score
        row_type_scores["discount"] = discount_score
        
        # PAYMENT signals and weights
        payment_score = 0.0
        payment_signals = []
        
        # Check for payment/tender/cash/card/EFT wording
        if re.search(r'\b(?:payment|paid|paid amount|amount paid|payment received|received|collected|payment method|payment type|payment mode|payment channel|payment gateway|payment processor|payment confirmation|payment status|payment complete|payment confirmed|payment accepted|payment approved|payment cleared|payment settled|payment finalized|payment completed|payment done|payment finished|payment processed|payment processed)\b', text_lower):
            payment_score += 8
            payment_signals.append("payment wording")
        
        # Check for full product structure (negative weight)
        if re.search(r'\b(?:product|item|sku|code|description|article|goods|merchandise)\b', text_lower) and \
           re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower) and \
           re.search(r'\b\d+(?:\.\d+)?\b', text_lower):
            payment_score -= 8
            payment_signals.append("full product structure")
        
        scores["payment"] = payment_score
        row_type_scores["payment"] = payment_score
        
        # CREDIT signals and weights
        credit_score = 0.0
        credit_signals = []
        
        # Check for credit/credit note wording
        if re.search(r'\b(?:credit|credit note|credit memo|credit adjustment|credit amount|credit balance|credit refund|credit voucher|credit card|credit card refund|credit card adjustment|credit card chargeback|credit card reversal|credit card dispute|credit card refund|credit card return|credit card reversal|credit card chargeback|credit card dispute|credit card refund|credit card return)\b', text_lower):
            credit_score += 8
            credit_signals.append("credit wording")
        
        # Check for negative amount (if present)
        if re.search(r'\b(?:-|minus)\b', text_lower):
            credit_score += 2
            credit_signals.append("negative amount")
        
        scores["credit"] = credit_score
        row_type_scores["credit"] = credit_score
        
        # RETURN signals and weights
        return_score = 0.0
        return_signals = []
        
        # Check for return/refund/bottle return wording
        if re.search(r'\b(?:return|returned|returning|return item|return goods|return product|return merchandise|return policy|return reason|return code|return note|return slip|return form|return request|return authorization|return approval|return confirmation|return receipt|return invoice|return order|return shipment|return tracking|return status|return date|return reason|return type|return category|return reason code|return reason description|return reason category|return reason group|return reason type|return reason class|return reason level|return reason priority|return reason severity|return reason impact|return reason cause|return reason root cause|return reason solution|return reason fix|return reason resolution|return reason action|return reason steps|return reason procedure|return reason process|return reason workflow|return reason flow|return reason sequence|return reason order|return reason hierarchy|return reason structure|return reason organization|return reason classification|return reason categorization|return reason grouping|return reason grouping|return reason clustering|return reason segmentation|return reason targeting|return reason selection|return reason filtering|return reason sorting|return reason ranking|return reason scoring|return reason weighting|return reason prioritization|return reason optimization|return reason improvement|return reason enhancement|return reason upgrade|return reason update|return reason modification|return reason adjustment|return reason correction|return reason fix|return reason solution|return reason resolution|return reason action|return reason steps|return reason procedure|return reason process|return reason workflow|return reason flow|return reason sequence|return reason order|return reason hierarchy|return reason structure|return reason organization|return reason classification|return reason categorization|return reason grouping|return reason grouping|return reason clustering|return reason segmentation|return reason targeting|return reason selection|return reason filtering|return reason sorting|return reason ranking|return reason scoring|return reason weighting|return reason prioritization|return reason optimization|return reason improvement|return reason enhancement|return reason upgrade|return reason update|return reason modification|return reason adjustment|return reason correction|return reason fix|return reason solution|return reason resolution|return reason action|return reason steps|return reason procedure|return reason process|return reason workflow|return reason flow|return reason sequence|return reason order|return reason hierarchy|return reason structure|return reason organization|return reason classification|return reason categorization|return reason grouping|return reason grouping|return reason clustering|return reason segmentation|return reason targeting|return reason selection|return reason filtering|return reason sorting|return reason ranking|return reason scoring|return reason weighting|return reason prioritization|return reason optimization|return reason improvement|return reason enhancement|return reason upgrade|return reason update|return reason modification|return reason adjustment|return reason correction)\b', text_lower):
            return_score += 8
            return_signals.append("return wording")
        
        scores["return"] = return_score
        row_type_scores["return"] = return_score
        
        # SERVICE_CHARGE signals and weights
        service_charge_score = 0.0
        service_charge_signals = []
        
        # Check for service/admin/handling charge wording
        if re.search(r'\b(?:service|service charge|service fee|service cost|service amount|service price|service rate|admin|handling|handling charge)\b', text_lower):
            service_charge_score += 8
            service_charge_signals.append("service charge wording")
        
        scores["service_charge"] = service_charge_score
        row_type_scores["service_charge"] = service_charge_score
        
        # HEADER signals and weights
        header_score = 0.0
        header_signals = []
        
        # Check for header vocabulary terms
        if re.search(r'\b(?:invoice|invoice number|invoice date|invoice due|invoice total|invoice amount|invoice sum|invoice value|invoice price|invoice cost|invoice payment|invoice status|invoice type|invoice category|invoice class|invoice group|invoice section|invoice part|invoice component|invoice element|invoice feature|invoice attribute|invoice property|invoice characteristic|invoice quality|invoice standard|invoice specification|invoice description|invoice details|invoice information|invoice data|invoice record|invoice entry|invoice item|invoice line|invoice row|invoice column|invoice field)\b', text_lower):
            header_score += 8
            header_signals.append("header vocabulary")
        
        # Check for no product numeric structure (positive weight)
        if not (re.search(r'\b(?:product|item|sku|code|description|article|goods|merchandise)\b', text_lower) and \
                re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower) and \
                re.search(r'\b\d+(?:\.\d+)?\b', text_lower)):
            header_score += 3
            header_signals.append("no product structure")
        
        scores["header"] = header_score
        row_type_scores["header"] = header_score
        
        # FOOTER signals and weights
        footer_score = 0.0
        footer_signals = []
        
        # Check for banking/account/terms/thank you/footer wording
        if re.search(r'\b(?:footer|page|total|amount|payment|due|balance|remaining|outstanding|paid|settled|cleared|final|complete|done|finished|processed|approved|accepted|confirmed|authorized|approved|signed|signature|date|time|company|address|contact|phone|email|website|terms|conditions|disclaimer|copyright|license|agreement|contract|policy|procedure|process|workflow|flow|sequence|order|reference|number|id|identifier|code|key|token|credential|password|login|account|profile|user|member|client|customer|supplier|vendor|provider|partner|affiliate|associate|collaborator|contributor|developer|engineer|technician|specialist|expert|consultant|advisor|advisor|manager|supervisor|leader|head|director|executive|officer|administrator|admin|operator|staff|employee|worker|personnel|team|group|department|division|section|unit|facility|location|site|place|area|zone|region|district|state|province|territory|country|nation|world|global|international|local|regional|national|community|organization|institution|corporation|company|enterprise|business|firm|shop|store|retail|commerce|trade|market|exchange|platform|portal|website|web|digital|online|virtual|remote|cloud|network|internet|connection|communication|contact|link|url|address|domain|host|server|machine|computer|device|equipment|hardware|software|application|program|code|script|database|data|information|knowledge|intelligence|wisdom|understanding|awareness|perception|recognition|identification|detection|observation|measurement|analysis|evaluation|assessment|review|inspection|audit|check|verification|validation|confirmation|approval|acceptance|authorization|permission|right|privilege|access|entry|admission|invitation|engagement|participation|involvement|commitment|dedication|devotion|loyalty|faithfulness|trust|confidence|reliability|dependability|stability|consistency|uniformity|regularity|frequency|occurrence|event|incident|case|instance|example|sample|model|pattern|template|format|layout|design|structure|framework|architecture|system|method|approach|technique|strategy|tactic|plan|scheme|proposal|idea|concept|theory|principle|rule|law|regulation|policy|guideline|standard|benchmark|criteria|requirement|condition|term|clause|provision|article|paragraph|sentence|phrase|word|letter|character|symbol|sign|mark|logo|brand|name|title|caption|heading|subheading|subtitle|tag|label|descriptor|attribute|property|feature|quality|characteristic|trait|aspect|dimension|element|component|part|portion|segment|section|subsection|chapter|volume|book|publication|document|paper|report|study|research|investigation|exploration|discovery|finding|conclusion|outcome|result|effect|impact|consequence|implication|meaning|interpretation|understanding|comprehension|knowledge|wisdom|insight|perspective|viewpoint|opinion|judgment|decision|choice|selection|option|alternative|possibility|potential|capability|capacity|ability|skill|talent|gift|aptitude|competence|proficiency|expertise|mastery|virtuosity|performance|execution|achievement|success|victory|triumph|glory|honor|recognition|award|prize|reward|recognition|celebration|honoring|appreciation|gratitude|thanks|acknowledgment|recognition|credit|kudos|commendation|acclaim|praise|glory|fame|renown|reputation|standing|prestige|status|position|rank|grade|level|degree|scale|rating|score|mark|grade|classification|category|type|kind|sort|variety|species|breed|strain|line|version|edition|release|update|patch|fix|correction|amendment|modification|revision|alteration|change|modification|adjustment|tweak|fine-tuning|optimization|improvement|enhancement|upgrade|enhancement|refinement|polish|finish|completion|closure|termination|end|conclusion|close|wrap-up)\b', text_lower):
            footer_score += 8
            footer_signals.append("footer wording")
        
        # Check for full product structure (negative weight)
        if re.search(r'\b(?:product|item|sku|code|description|article|goods|merchandise)\b', text_lower) and \
           re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower) and \
           re.search(r'\b\d+(?:\.\d+)?\b', text_lower):
            footer_score -= 8
            footer_signals.append("full product structure")
        
        scores["footer"] = footer_score
        row_type_scores["footer"] = footer_score
        
        # Find the highest scoring row type
        max_score = max(scores.values())
        max_score_type = None
        second_max_score = 0.0
        second_max_type = None
        
        # Find the highest and second highest scores
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_scores:
            max_score_type = sorted_scores[0][0]
            max_score = sorted_scores[0][1]
            if len(sorted_scores) > 1:
                second_max_type = sorted_scores[1][0]
                second_max_score = sorted_scores[1][1]
        
        # Determine if we should return UNKNOWN
        unknown_threshold = 0.0  # Minimum evidence threshold
        score_difference_threshold = 0.5  # Minimum difference between top two scores
        
        # Check if we should return UNKNOWN
        if max_score <= unknown_threshold or (second_max_type and (max_score - second_max_score) < score_difference_threshold):
            row_type = RowType.UNKNOWN
            confidence = 0.0
            reasons.append("No clear winner or insufficient evidence")
        else:
            # Choose the highest scoring type
            row_type = RowType(max_score_type)
            
            # Calculate confidence based on score strength and margin
            if max_score > 0:
                # Confidence based on how much better the top score is
                if second_max_type:
                    score_margin = max_score - second_max_score
                    confidence = min(1.0, max_score / 20.0 + score_margin / 10.0)
                else:
                    confidence = min(1.0, max_score / 20.0)
            else:
                confidence = 0.0
            
            # Apply additional confidence penalties for conflicting signals
            if row_type == RowType.PRODUCT:
                # Check for conflicting signals
                if re.search(r'\b(?:total|grand total|final total|subtotal|vat|tax)\b', text_lower):
                    conflicting_signals.append("Conflicting signal: Total/Subtotal/VAT detected in product row")
                    confidence *= 0.7  # Reduce confidence due to conflict
            elif row_type == RowType.VAT:
                # Check for conflicting signals
                if re.search(r'\b(?:product|item|sku|code|description|article|goods|merchandise)\b', text_lower) and \
                   re.search(r'\b(?:kg|g|l|ml|pcs|piece|unit|box|pack|carton|bottle|jar|bag|can|tube|roll|sheet|set|pair|dozen)\b', text_lower) and \
                   re.search(r'\b\d+(?:\.\d+)?\b', text_lower):
                    conflicting_signals.append("Conflicting signal: Product structure detected in VAT row")
                    confidence *= 0.8  # Reduce confidence due to conflict
        
        # Collect all matched signals
        all_matched_signals = []
        for row_type_enum, patterns in self._patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    all_matched_signals.append(pattern)
        
        # Add specific reasons based on the classification
        if row_type == RowType.PRODUCT:
            reasons.append("Product-like content detected")
        elif row_type == RowType.VAT:
            reasons.append("VAT-like content detected")
        elif row_type == RowType.TOTAL:
            reasons.append("Total-like content detected")
        elif row_type == RowType.DISCOUNT:
            reasons.append("Discount-like content detected")
        elif row_type == RowType.DELIVERY:
            reasons.append("Delivery-like content detected")
        elif row_type == RowType.RETURN:
            reasons.append("Return-like content detected")
        elif row_type == RowType.CREDIT:
            reasons.append("Credit-like content detected")
        elif row_type == RowType.SERVICE_CHARGE:
            reasons.append("Service charge-like content detected")
        elif row_type == RowType.SUBTOTAL:
            reasons.append("Subtotal-like content detected")
        elif row_type == RowType.PAYMENT:
            reasons.append("Payment-like content detected")
        elif row_type == RowType.HEADER:
            reasons.append("Header-like content detected")
        elif row_type == RowType.FOOTER:
            reasons.append("Footer-like content detected")
        else:
            reasons.append("Unknown content type")
        
        return ClassificationResult(
            row_type=row_type,
            confidence=confidence,
            reasons=reasons,
            matched_signals=all_matched_signals,
            conflicting_signals=conflicting_signals,
            row_type_scores=row_type_scores,
            winning_score=max_score,
            second_place_type=second_max_type or "none",
            second_place_score=second_max_score,
            score_margin=max_score - second_max_score if second_max_type else 0.0
        )
    
    def classify_many(self, rows: List[str]) -> List[ClassificationResult]:
        """
        Classify multiple rows at once.
        
        Args:
            rows: List of row texts to classify
            
        Returns:
            List of ClassificationResult objects
        """
        return [self.classify(row) for row in rows]


# Example usage:
if __name__ == "__main__":
    classifier = InvoiceRowClassifier()
    
    # Test examples
    test_rows = [
        "1234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012......",
        "SUBTOTAL",
        "VAT 15%",
        "TOTAL",
        "Delivery Fee",
        "Discount 10%",
        "Return of damaged goods",
        "Service Charge",
        "Invoice Header Info",
        "Invoice Footer Info"
    ]
    
    for i, row in enumerate(test_rows):
        result = classifier.classify(row)
        print(f"Row {i+1}: {row[:50]}...")
        print(f"  Type: {result.row_type.value}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Reasons: {', '.join(result.reasons)}")
        print(f"  Winning Score: {result.winning_score}")
        print(f"  Second Place: {result.second_place_type} ({result.second_place_score})")
        print(f"  Score Margin: {result.score_margin}")
        print()
