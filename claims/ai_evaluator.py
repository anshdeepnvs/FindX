import os
import json
import re
from django.conf import settings


def evaluate_claim_with_llm(finder_hidden_details, claimant_answers, item_title, public_desc):
    """
    Evaluates claimant answers against finder's hidden details using Google Gemini API.
    Returns a dict with: match_score, confidence_level, reasoning_summary, matching_points, discrepancy_points.
    """
    api_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are an expert AI Anti-Fraud & Ownership Verification Engine for a global Lost & Found platform.

Item Context:
- Item: {item_title}
- Public Description: {public_desc}

Finder's Ground Truth (STRICTLY CONFIDENTIAL - Never shown to claimant):
"{finder_hidden_details}"

Claimant's Submission (Claiming to be the genuine owner answering blind questions):
"{claimant_answers}"

Your Task:
Analyze whether the claimant is the true owner or an imposter/scammer guessing details.
Check:
- Specific unique markers mentioned (stickers, serial snippets, wallpapers, card names, scratches, internal items).
- Direct contradictions or generic guesses.

Return ONLY a valid JSON object with the following schema:
{{
  "match_score": <number between 0 and 100>,
  "confidence_level": "<HIGH | MODERATE | LOW | FRAUD_ALERT>",
  "reasoning_summary": "<2-3 sentences explaining the assessment>",
  "matching_points": "<bulleted list of confirmed matching attributes>",
  "discrepancy_points": "<bulleted list of conflicting, suspicious, or unverified claims>"
}}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        data = json.loads(response.text)
        return data
    except Exception as e:
        print(f"Gemini LLM evaluation failed: {e}. Falling back to local heuristic analysis.")
        return None


def evaluate_claim_local_heuristic(finder_hidden_details, claimant_answers, item_title=""):
    """
    Robust local rule-based heuristic evaluator when Gemini API key is absent or offline.
    Uses token overlap, keyword matching, and similarity calculations.
    """
    if not finder_hidden_details or not claimant_answers:
        return {
            "match_score": 10.0,
            "confidence_level": "LOW",
            "reasoning_summary": "Insufficient information provided in secret details or claimant submission.",
            "matching_points": "No matching details found.",
            "discrepancy_points": "Details are too vague to determine ownership."
        }

    # Normalize texts
    stop_words = {"the", "a", "an", "is", "in", "it", "of", "and", "or", "with", "my", "i", "to", "at", "for", "on", "was", "this", "that"}
    
    def tokenize(text):
        tokens = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower())
        return [t for t in tokens if t not in stop_words]

    finder_tokens = set(tokenize(finder_hidden_details))
    claimant_tokens = set(tokenize(claimant_answers))

    if not finder_tokens:
        return {
            "match_score": 50.0,
            "confidence_level": "MODERATE",
            "reasoning_summary": "Finder did not specify detailed private marks. Manual review recommended.",
            "matching_points": "General claim submitted.",
            "discrepancy_points": "No private baseline to compare against."
        }

    # Intersecting keywords
    overlap = finder_tokens.intersection(claimant_tokens)
    overlap_ratio = len(overlap) / max(len(finder_tokens), 1)

    # Substring matches (e.g. serial parts or full phrase snippets)
    raw_finder = finder_hidden_details.lower()
    raw_claimant = claimant_answers.lower()
    
    extra_boost = 0
    matched_phrases = list(overlap)
    
    # Check if numbers match (serials, money, IDs)
    finder_nums = set(re.findall(r"\b\d+\b", raw_finder))
    claimant_nums = set(re.findall(r"\b\d+\b", raw_claimant))
    common_nums = finder_nums.intersection(claimant_nums)
    if common_nums:
        extra_boost += 25 * len(common_nums)
        for num in common_nums:
            matched_phrases.append(f"Number/Identifier '{num}' matches exactly")

    # Calculate raw score
    calculated_score = min(100.0, (overlap_ratio * 70.0) + extra_boost)
    calculated_score = round(max(5.0, calculated_score), 1)

    # Determine confidence level
    if calculated_score >= 70.0:
        confidence = "HIGH"
        summary = "Strong correlation detected between claimant's description and the finder's private notes."
    elif calculated_score >= 40.0:
        confidence = "MODERATE"
        summary = "Moderate alignment detected. Some key terms match, but verify supporting proof before handover."
    elif calculated_score >= 20.0:
        confidence = "LOW"
        summary = "Low similarity score. Claimant's responses share very few identifying features with the hidden details."
    else:
        confidence = "FRAUD_ALERT"
        summary = "Critical mismatch. Claimant's response contradicts or fails to identify any private marks. Potential false claim."

    matching_str = "\n".join([f"• {m}" for m in matched_phrases]) if matched_phrases else "• No significant private terms matched."
    discrepancy_str = "• Review claimant's purchase receipt / proof image to confirm authenticity." if calculated_score < 80 else "• None apparent from text analysis."

    return {
        "match_score": calculated_score,
        "confidence_level": confidence,
        "reasoning_summary": summary,
        "matching_points": matching_str,
        "discrepancy_points": discrepancy_str,
    }


def evaluate_claim(claim):
    """
    Main evaluation entry point. Evaluates an ItemClaim and creates/updates AIAnalysisResult.
    """
    from .models import AIAnalysisResult

    item = claim.item
    hidden = item.hidden_details
    answers = claim.claimed_answers

    # Try LLM first
    result = evaluate_claim_with_llm(
        finder_hidden_details=hidden,
        claimant_answers=answers,
        item_title=item.title,
        public_desc=item.public_description
    )

    # Fallback to local heuristic
    if not result:
        result = evaluate_claim_local_heuristic(hidden, answers, item.title)

    # Save or update AIAnalysisResult
    ai_record, created = AIAnalysisResult.objects.update_or_create(
        claim=claim,
        defaults={
            "match_score": result.get("match_score", 0.0),
            "confidence_level": result.get("confidence_level", "LOW"),
            "reasoning_summary": result.get("reasoning_summary", ""),
            "matching_points": result.get("matching_points", ""),
            "discrepancy_points": result.get("discrepancy_points", ""),
        }
    )
    return ai_record
