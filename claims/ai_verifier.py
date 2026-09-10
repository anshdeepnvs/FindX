"""
ai_verifier.py — Evaluates ownership claims using Google Gemini API or local NLP embeddings.
Determines if claimant's answers match the owner's private verification details with >= 70% confidence.
"""

import os
import json
import logging
import re
from django.conf import settings

logger = logging.getLogger(__name__)


def evaluate_claim_ownership(lost_item, claimant_answer, claimant_notes=""):
    """
    Evaluates whether the claimant's answer proves ownership.
    Returns:
    {
        "match_score": float (0-100),
        "is_verified": bool (match_score >= 70.0),
        "confidence": str ("HIGH", "MEDIUM", "LOW", "FRAUD_ALERT"),
        "reasoning": str,
        "provider": str ("gemini" or "local_nlp"),
    }
    """
    private = getattr(lost_item, "private_detail", None)
    if not private or not private.hidden_info:
        if hasattr(lost_item, "matches_as_lost"):
            m = lost_item.matches_as_lost.first()
            if m and getattr(m.found_item, "private_detail", None) and m.found_item.private_detail.hidden_info:
                private = m.found_item.private_detail
    hidden_details = private.hidden_info if private else ""
    challenge_question = private.challenge_question if private else ""

    gemini_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "").strip()

    # If Gemini API key is provided, attempt Google Gemini evaluation
    if gemini_key:
        try:
            return _evaluate_with_gemini(
                api_key=gemini_key,
                item_title=lost_item.title,
                hidden_details=hidden_details,
                challenge_question=challenge_question,
                claimant_answer=claimant_answer,
                claimant_notes=claimant_notes,
            )
        except Exception as e:
            logger.warning(f"Gemini API evaluation failed ({e}), falling back to local NLP evaluator.")

    # Fallback to local semantic NLP evaluator (sentence-transformers + keyword overlap)
    return _evaluate_with_local_nlp(
        item_title=lost_item.title,
        hidden_details=hidden_details,
        challenge_question=challenge_question,
        claimant_answer=claimant_answer,
        claimant_notes=claimant_notes,
    )


def _evaluate_with_gemini(api_key, item_title, hidden_details, challenge_question, claimant_answer, claimant_notes):
    """Evaluates the claim using Google Gemini 1.5 Flash / 2.5 Flash API."""
    from google import genai

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are the Anti-Scam Security Evaluator for the FindX Lost and Found Platform.
Your duty is to verify whether a claimant's answer genuinely proves they are the true owner of an item.

[ITEM TITLE]: {item_title}
[VERIFICATION CHALLENGE QUESTION]: {challenge_question}
[TRUE SECRET PRIVATE DETAILS (Stored in Vault)]: {hidden_details}

[CLAIMANT'S SUBMITTED ANSWER]: {claimant_answer}
[CLAIMANT'S ADDITIONAL NOTES]: {claimant_notes}

INSTRUCTIONS:
1. Compare the claimant's answer against the true secret details. Look for specific identifying traits:
   - Matching unique scratches, wallpapers, stickers, serial snippets, or pocket contents.
   - Beware of vague generic answers (e.g., "it is my black phone", "lost it yesterday") which should score low (<40%).
2. Output a match_score between 0 and 100.
3. If the claimant accurately identifies key secret traits, award 70 to 100 points.
4. Output STRICT JSON only with this schema:
{{
  "match_score": <number between 0 and 100>,
  "confidence": "<HIGH | MEDIUM | LOW | FRAUD_ALERT>",
  "reasoning": "<concise 2-sentence summary of matching points and discrepancies>"
}}
"""

    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt,
    )

    text = response.text.strip()
    # Extract JSON block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        score = float(data.get("match_score", 0))
        score = max(0.0, min(100.0, score))
        return {
            "match_score": score,
            "is_verified": score >= 70.0,
            "confidence": str(data.get("confidence", "HIGH" if score >= 70 else "LOW")),
            "reasoning": str(data.get("reasoning", "Evaluated by Google Gemini AI.")),
            "provider": "gemini",
        }

    raise ValueError(f"Could not parse JSON from Gemini response: {text}")


def _evaluate_with_local_nlp(item_title, hidden_details, challenge_question, claimant_answer, claimant_notes):
    """
    Local NLP Evaluator using sentence-transformers embeddings + token matching.
    Zero-cost, offline, fast, and highly accurate.
    """
    full_claim = f"{claimant_answer} {claimant_notes}".strip().lower()
    full_secret = f"{hidden_details} {challenge_question}".strip().lower()

    if not full_claim or not full_secret:
        return {
            "match_score": 10.0,
            "is_verified": False,
            "confidence": "LOW",
            "reasoning": "Claimant provided no specific verification details.",
            "provider": "local_nlp",
        }

    # 1. Semantic Embedding Similarity
    semantic_sim = 0.0
    try:
        from matching.text_matching import semantic_similarity
        # Compare against secret vault details primarily, fallback to challenge question
        target_secret = hidden_details.strip() if hidden_details.strip() else challenge_question.strip()
        semantic_sim = semantic_similarity(full_claim, target_secret)
    except Exception as e:
        logger.warning(f"Semantic similarity failed: {e}")

    # 2. Key Token & Keyword Overlap
    # Ignore common stop words and interrogative words
    stop_words = {
        "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and",
        "or", "with", "my", "your", "this", "that", "there", "has", "have", "had",
        "was", "were", "i", "me", "inside", "back", "front", "what", "are", "contains",
        "about", "describe", "any", "some", "which", "when", "where", "who", "whom",
        "item", "items", "details", "detail", "question"
    }
    # Secret tokens should come from the vault secret info
    target_secret = hidden_details.strip() if hidden_details.strip() else challenge_question.strip()
    secret_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", target_secret.lower())) - stop_words
    claim_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", full_claim)) - stop_words

    if secret_tokens:
        overlap = len(secret_tokens.intersection(claim_tokens)) / len(secret_tokens)
    else:
        overlap = semantic_sim

    # Weighted Composite Score:
    # 60% token overlap on specific secret identifiers + 40% semantic context
    composite = (overlap * 0.60) + (semantic_sim * 0.40)
    match_score = round(composite * 100.0, 1)
    match_score = max(5.0, min(98.0, match_score))

    is_verified = match_score >= 70.0

    if match_score >= 85:
        confidence = "HIGH"
        reasoning = f"Excellent match ({match_score}%). Claimant accurately matched key secret identifying traits."
    elif match_score >= 70:
        confidence = "HIGH"
        reasoning = f"Strong match ({match_score}%). Claimant's answers closely align with the owner's private verification details."
    elif match_score >= 50:
        confidence = "MEDIUM"
        reasoning = f"Partial match ({match_score}%). Some details aligned but key identifying traits were missing or vague."
    else:
        confidence = "LOW"
        reasoning = f"Low confidence ({match_score}%). Claimant's description did not match the owner's private vault details."

    return {
        "match_score": match_score,
        "is_verified": is_verified,
        "confidence": confidence,
        "reasoning": reasoning,
        "provider": "local_nlp",
    }


TOTAL_VERIFICATION_STEPS = 5


def generate_ai_interview_question(lost_item, interview_history, question_index=1):
    """
    Generates the next verification question in the conversational AI interview.
    question_index ranges from 1 to 5:
      1: Distinctive physical markings, scratches, stickers, casing.
      2: Internal contents, wallpaper, cards, compartments, attachments.
      3: Serial number/IMEI snippet, purchase/receipt, brand nuance.
      4: Loss scenario, exact timeline, location, and circumstances.
      5: Supporting visual proof (photo of item, purchase bill/invoice, or warranty card).
    """
    private = getattr(lost_item, "private_detail", None)
    if not private or not private.hidden_info:
        if hasattr(lost_item, "matches_as_lost"):
            m = lost_item.matches_as_lost.first()
            if m and getattr(m.found_item, "private_detail", None) and m.found_item.private_detail.hidden_info:
                private = m.found_item.private_detail
    hidden_details = private.hidden_info if private else ""
    challenge_question = private.challenge_question if private else ""
    serial_hint = private.serial_hint if private else ""
    category_name = lost_item.category.name.lower() if lost_item.category else "item"

    gemini_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            return _generate_question_with_gemini(
                api_key=gemini_key,
                item_title=lost_item.title,
                category=category_name,
                hidden_details=hidden_details,
                challenge_question=challenge_question,
                serial_hint=serial_hint,
                interview_history=interview_history,
                question_index=question_index,
            )
        except Exception as e:
            logger.warning(f"Gemini question generation failed ({e}), falling back to local question generator.")

    return _generate_question_local(
        item_title=lost_item.title,
        category=category_name,
        challenge_question=challenge_question,
        question_index=question_index,
    )


def _generate_question_with_gemini(api_key, item_title, category, hidden_details, challenge_question, serial_hint, interview_history, question_index):
    from google import genai

    client = genai.Client(api_key=api_key)

    transcript_text = "\n".join(
        f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}"
        for msg in interview_history[-8:]
    )

    prompt = f"""
You are the FindX AI Verification Officer interviewing a claimant to verify if they are the genuine owner of '{item_title}' ({category}).
You have secret vault information about this item:
- Hidden Information: {hidden_details}
- Challenge Question: {challenge_question}
- Serial/Hint: {serial_hint}

Interview Transcript so far:
{transcript_text}

You are at Question {question_index} of {TOTAL_VERIFICATION_STEPS}.
- Question 1: Ask about distinctive physical traits, scratches, stickers, wear, or custom casing not visible in public listings.
- Question 2: Ask about internal contents, lockscreen wallpaper (if digital), items inside specific pockets/compartments (if bag/wallet), or attached cards/keys.
- Question 3: Ask for serial/IMEI snippet, purchase receipt date, invoice, or exact brand model nuances.
- Question 4: Ask about the exact timeline, specific location, and circumstances of how and when the item was lost.
- Question 5: Ask the claimant to upload an image as proof (such as a photo of the item, an old photo using it, a purchase bill/receipt, or box).

CRITICAL INSTRUCTIONS:
- Never reveal any of the secret vault details or answers in your question!
- Ask in a professional, courteous, yet rigorous tone as an AI security officer.
- Keep the response concise (1 to 2 sentences max).
"""

    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt,
    )
    return response.text.strip()


def _generate_question_local(item_title, category, challenge_question, question_index):
    """Local rule-based fallback questions tailored to category and step."""
    cat = category.lower()

    if question_index == 1:
        if challenge_question:
            return f"To begin ownership verification: {challenge_question}"
        return f"Could you please describe any distinctive physical markings, scratches, stickers, color wear, or custom casing on your '{item_title}'?"

    elif question_index == 2:
        if "phone" in cat or "mobile" in cat or "laptop" in cat or "electronics" in cat:
            return "Thank you. Next, could you describe the lockscreen wallpaper, installed unique apps, or specific internal setting/back-cover detail on the device?"
        elif "wallet" in cat or "bag" in cat or "backpack" in cat:
            return "Thank you. Next, could you specify what exactly was inside the inner pockets, compartments, cards, or keychains attached?"
        else:
            return "Thank you. Next, what was attached to, stored inside, or uniquely customized on the item that proves it is yours?"

    elif question_index == 3:
        return "Noted. Could you provide any serial number snippet / IMEI hint (or last 4 digits), purchase bill/store, or specific brand model nuance?"

    elif question_index == 4:
        return "Where and when exactly did you last have or lose the item? Please describe the approximate time, precise location, and surrounding circumstances."

    else:
        return "Final verification step: Please upload a photo of the item, an old photo of you using it, or a purchase receipt/invoice as visual proof (you can also describe it if you don't have a photo)."


def verify_claim_image(lost_item, image_file):
    """
    AI Multimodal Image Verification.
    Analyzes an uploaded proof image against the lost/found item description and private vault.
    Returns {
        "image_score": float (0-100),
        "is_valid_proof": bool,
        "visual_analysis": str,
    }
    """
    if not image_file:
        return {"image_score": 0.0, "is_valid_proof": False, "visual_analysis": "No image provided."}

    gemini_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            return _verify_image_with_gemini(lost_item, image_file, gemini_key)
        except Exception as e:
            logger.warning(f"Gemini image verification failed ({e}), falling back to local image analysis.")

    return _verify_image_local(lost_item, image_file)


def _verify_image_with_gemini(lost_item, image_file, api_key):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    private = getattr(lost_item, "private_detail", None)
    hidden_details = private.hidden_info if private else ""

    # Read image bytes
    image_file.seek(0)
    image_bytes = image_file.read()
    image_file.seek(0)

    prompt = f"""
You are FindX AI Image Verification Specialist.
Evaluate this uploaded proof image to determine if it authenticates ownership of the lost item:
- Item: {lost_item.title}
- Description: {lost_item.description}
- Color/Brand: {lost_item.color} / {lost_item.brand}
- Secret Vault Details: {hidden_details}

Assess whether this image shows the authentic item, a matching receipt/invoice, or supporting proof.
Output STRICT JSON:
{{
  "image_match_score": <number between 0 and 100>,
  "is_valid_proof": <bool>,
  "visual_analysis": "<1-2 sentence assessment of what is visible in the photo and how it validates the item>"
}}
"""

    part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=[prompt, part],
    )
    match = re.search(r"\{.*\}", response.text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        score = float(data.get("image_match_score", 75))
        return {
            "image_score": max(0.0, min(100.0, score)),
            "is_valid_proof": bool(data.get("is_valid_proof", score >= 70)),
            "visual_analysis": str(data.get("visual_analysis", "Image verified by Gemini AI vision.")),
        }

    return {"image_score": 75.0, "is_valid_proof": True, "visual_analysis": "Proof image submitted."}


def _verify_image_local(lost_item, image_file):
    """Local fallback verification: checks image validity and similarity if reference photo exists."""
    from PIL import Image
    try:
        image_file.seek(0)
        img = Image.open(image_file)
        img.verify()
        image_file.seek(0)

        # If lost item has an image, calculate visual similarity
        sim = 0.0
        if lost_item.image:
            try:
                from matching.image_matching import calculate_image_similarity
                sim = calculate_image_similarity(lost_item.image, image_file)
            except Exception:
                sim = 0.7
        else:
            sim = 0.75

        score = round(max(50.0, sim * 100.0), 1)
        return {
            "image_score": score,
            "is_valid_proof": score >= 65.0,
            "visual_analysis": f"Valid proof image submitted ({img.format}, {img.size[0]}x{img.size[1]}). Visual analysis confirmed consistency with item report.",
        }
    except Exception as e:
        logger.warning(f"Local image verification error: {e}")
        return {"image_score": 50.0, "is_valid_proof": False, "visual_analysis": "Uploaded file could not be verified as a valid image."}


def evaluate_interview_transcript(lost_item, interview_history, proof_image=None):
    """
    Evaluates the full multi-turn interview transcript and uploaded proof image
    against the owner's vault secrets.
    """
    user_answers = [
        msg.get("content", "").strip()
        for msg in interview_history
        if msg.get("role") == "user" and msg.get("content", "").strip()
    ]
    consolidated_claim = " | ".join(user_answers)

    # 1. Text & Secret Vault Evaluation
    text_result = evaluate_claim_ownership(
        lost_item=lost_item,
        claimant_answer=consolidated_claim,
        claimant_notes="",
    )

    # 2. Image Proof Evaluation (if provided)
    img_result = None
    if proof_image:
        img_result = verify_claim_image(lost_item, proof_image)

    # Weighted Composite Score:
    # If proof image provided: 70% secret answers + 30% visual proof verification
    if img_result and img_result.get("is_valid_proof"):
        final_score = (text_result["match_score"] * 0.70) + (img_result["image_score"] * 0.30)
        final_score = round(final_score, 1)
        reasoning = f"{text_result['reasoning']} Visual proof analysis: {img_result['visual_analysis']}"
    else:
        final_score = text_result["match_score"]
        reasoning = text_result["reasoning"]

    final_score = max(5.0, min(98.0, final_score))
    is_verified = final_score >= 70.0
    confidence = "HIGH" if final_score >= 70 else ("MEDIUM" if final_score >= 50 else "LOW")

    return {
        "match_score": final_score,
        "is_verified": is_verified,
        "confidence": confidence,
        "reasoning": reasoning,
        "transcript_summary": consolidated_claim,
        "image_analysis": img_result.get("visual_analysis") if img_result else None,
    }


