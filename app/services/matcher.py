"""
Identity Resolution Engine with match confidence scoring
"""
import re
from typing import Dict, Any, List
from app.models import MatchConfidence, MatchedBenefit
from app.config import MATCH_HIGH_THRESHOLD, MATCH_MEDIUM_THRESHOLD

def normalize_string(s: str) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r'[^\w\s]', ' ', s)
    # Common address abbreviation normalization
    replacements = {
        r'\bave\b': 'avenue',
        r'\bst\b': 'street',
        r'\brd\b': 'road',
        r'\bdr\b': 'drive',
        r'\bln\b': 'lane',
        r'\bblvd\b': 'boulevard',
        r'\bapt\b': 'apartment',
    }
    for pat, rep in replacements.items():
        s = re.sub(pat, rep, s)
    return re.sub(r'\s+', ' ', s).strip()

def extract_name_tokens(raw_name: str) -> set:
    norm = normalize_string(raw_name)
    tokens = set(norm.split())
    return tokens

def compute_match_confidence(rest_rec: Dict[str, Any], xml_rec: Dict[str, Any]) -> MatchConfidence:
    score = 0.0
    reasons = []

    # 1. Date of Birth match (weight 0.45)
    rest_dob = rest_rec.get('date_of_birth', '').strip()
    xml_dob = xml_rec.get('born', '').strip()

    if rest_dob and xml_dob and rest_dob == xml_dob:
        score += 0.45
        reasons.append("Exact DOB match")
    elif rest_dob and xml_dob:
        reasons.append(f"DOB mismatch ({rest_dob} vs {xml_dob})")

    # 2. Name token match (weight 0.35)
    rest_fn = rest_rec.get('first_name', '')
    rest_ln = rest_rec.get('last_name', '')
    rest_full_name = f"{rest_fn} {rest_ln}"
    rest_name_tokens = extract_name_tokens(rest_full_name)

    xml_name = xml_rec.get('name', '')
    xml_name_tokens = extract_name_tokens(xml_name)

    if rest_name_tokens and xml_name_tokens:
        intersection = rest_name_tokens.intersection(xml_name_tokens)
        union = rest_name_tokens.union(xml_name_tokens)
        token_similarity = len(intersection) / len(union) if union else 0.0
        score += (token_similarity * 0.35)
        if token_similarity >= 0.8:
            reasons.append("High name token match")
        elif token_similarity > 0.0:
            reasons.append(f"Partial name match ({int(token_similarity*100)}%)")

    # 3. Address & Town match (weight 0.20)
    rest_addr = normalize_string(rest_rec.get('address_line', ''))
    xml_addr = normalize_string(xml_rec.get('addr', ''))
    rest_city = normalize_string(rest_rec.get('city', ''))
    xml_town = normalize_string(xml_rec.get('town', ''))

    addr_score = 0.0
    if rest_addr and xml_addr and (rest_addr == xml_addr or rest_addr in xml_addr or xml_addr in rest_addr):
        addr_score += 0.15
        reasons.append("Address match")

    if rest_city and xml_town and rest_city == xml_town:
        addr_score += 0.05
        reasons.append("Town match")

    score += addr_score
    score = round(score, 2)

    if score >= MATCH_HIGH_THRESHOLD:
        level = "HIGH"
    elif score >= MATCH_MEDIUM_THRESHOLD:
        level = "MEDIUM"
    else:
        level = "UNMATCHED"

    return MatchConfidence(score=score, level=level, reasons=reasons)

def find_matching_benefits(rest_rec: Dict[str, Any], xml_records: List[Dict[str, Any]], min_threshold: float = MATCH_MEDIUM_THRESHOLD) -> List[MatchedBenefit]:
    matched = []
    for xrec in xml_records:
        conf = compute_match_confidence(rest_rec, xrec)
        if conf.score >= min_threshold:
            matched.append(MatchedBenefit(
                ref=xrec.get('ref', ''),
                name=xrec.get('name', ''),
                born=xrec.get('born', ''),
                addr=xrec.get('addr', ''),
                town=xrec.get('town', ''),
                benefit_code=xrec.get('benefit_code', ''),
                review_due=xrec.get('review_due', ''),
                match_confidence=conf
            ))
    # Sort matched by highest score
    matched.sort(key=lambda m: m.match_confidence.score, reverse=True)
    return matched
