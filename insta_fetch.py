import requests
import json
import re
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from config import ACCESS_TOKEN, IG_USER_ID, PERSPECTIVE_API_KEY

# Preview flag: True -> detect only, False -> delete
PREVIEW_MODE = True
TOXICITY_THRESHOLD = 0.75  # score (0..1) above which a comment is toxic

PERSPECTIVE_URL = "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"

# --- Runtime state for reports ---
deleted_comments_log = []      # [{id, text}]
seen_comment_ids = set()       # to avoid double-counting across refreshes
daily_counters = defaultdict(lambda: {"analyzed": 0, "toxic": 0, "deleted": 0})
top_words_counter = Counter()
totals = {"analyzed": 0, "toxic": 0, "deleted": 0}

STOPWORDS = {
    "the","a","an","and","or","but","to","of","in","on","for","with","at","by",
    "is","it","this","that","be","as","are","was","were","you","i","me","my",
    "we","they","them","he","she","his","her","our","your","yours","from","not","hai","look"
}


# --- Save stats to file ---
def save_stats():
    data = {
        "totals": totals,
        "daily_counters": daily_counters,
        "top_words": dict(top_words_counter),
        "seen_comment_ids": list(seen_comment_ids)  # save IDs
    }
    with open("stats.json", "w") as f:
        json.dump(data, f)

# --- Load stats from file ---
def load_stats():
    global totals, daily_counters, top_words_counter, seen_comment_ids
    try:
        with open("stats.json") as f:
            data = json.load(f)
            totals = data.get("totals", {"analyzed":0,"toxic":0,"deleted":0})
            daily_counters = defaultdict(lambda: {"analyzed":0,"toxic":0,"deleted":0}, data.get("daily_counters", {}))
            top_words_counter = Counter(data.get("top_words", {}))
            seen_comment_ids = set(data.get("seen_comment_ids", []))  # restore IDs
    except:
        pass
    
load_stats()

def _today_key():
    return datetime.utcnow().strftime("%Y-%m-%d")

def _tokenize(text):
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]

def analyze_comment(text):
    """Return toxicity score (0.0..1.0) or None on error."""
    try:
        payload = {
            "comment": {"text": text},
            "languages": ["en"],
            "requestedAttributes": {"TOXICITY": {}}
        }
        resp = requests.post(
            f"{PERSPECTIVE_URL}?key={PERSPECTIVE_API_KEY}",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"}
        )
        if resp.status_code != 200:
            print("Perspective API error:", resp.text)
            return None
        result = resp.json()
        score = result["attributeScores"]["TOXICITY"]["summaryScore"]["value"]
        return float(score)
    except Exception as e:
        print("analyze_comment exception:", e)
        return None

def delete_comment(comment_id):
    """Delete comment via Graph API."""
    try:
        url = f"https://graph.facebook.com/v21.0/{comment_id}"
        resp = requests.delete(url, params={"access_token": ACCESS_TOKEN})
        if resp.status_code == 200:
            print(f"Deleted comment {comment_id}")
            return True
        else:
            print("Delete failed:", resp.status_code, resp.text)
            return False
    except Exception as e:
        print("delete_comment exception:", e)
        return False

def fetch_and_moderate_comments():
    results = []
    try:
        media_url = f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media"
        params = {"fields": "id,caption", "access_token": ACCESS_TOKEN}
        media_resp = requests.get(media_url, params=params)
        if media_resp.status_code != 200:
            print("Error fetching media:", media_resp.text)
            return results

        media_data = media_resp.json().get("data", [])
        for media in media_data:
            media_id = media.get("id")
            if not media_id:
                continue

            comments_url = f"https://graph.facebook.com/v21.0/{media_id}/comments"
            comments_resp = requests.get(comments_url, params={"access_token": ACCESS_TOKEN})
            if comments_resp.status_code != 200:
                print("Error fetching comments for media", media_id, comments_resp.text)
                continue

            comments = comments_resp.json().get("data", [])
            for c in comments:
                comment_id = c.get("id")
                text = c.get("text", "")
                username = c.get("username", c.get("from", {}).get("username", "unknown"))
                if not comment_id or not text:
                    continue

                # --- Custom keyword + phrase matching ---
                TOXIC_KEYWORDS = {"fuck", "chutiya", "bastard", "idiot", "dog", "stupid", "loser", "jerk", "kutta", "dumb"}
                TOXIC_PHRASES = ["look like dog", "shut up", "go away"]

                custom_toxic = any(word in text.lower() for word in TOXIC_KEYWORDS) \
                               or any(phrase in text.lower() for phrase in TOXIC_PHRASES)

                # --- Score using Perspective API ---
                score = analyze_comment(text)
                if score is None:
                    toxicity_pct = 0.0
                    status = "Unknown"
                else:
                    toxicity_pct = round(score * 100, 2)
                    if score > TOXICITY_THRESHOLD or custom_toxic:
                        if PREVIEW_MODE:
                            status = "Preview (Toxic)"
                        else:
                            deleted = delete_comment(comment_id)
                            status = "Deleted" if deleted else "Delete Failed"
                    else:
                        status = "Safe"

                # --- Append results for dashboard ---
                results.append({
                    "comment": text,
                    "toxicity": toxicity_pct,
                    "status": status,
                    "username": username
                })

                # --- Update stats ---
                today = _today_key()

                # Count analyzed/toxic only once per comment
                if comment_id not in seen_comment_ids:
                    seen_comment_ids.add(comment_id)
                    totals["analyzed"] += 1
                    daily_counters[today]["analyzed"] += 1

                    if score is not None and (score > TOXICITY_THRESHOLD or custom_toxic):
                        totals["toxic"] += 1
                        daily_counters[today]["toxic"] += 1
                        top_words_counter.update(_tokenize(text))

                # Always count deletion for today, even if seen before
                if status == "Deleted":
                    totals["deleted"] += 1
                    daily_counters[today]["deleted"] += 1
                    if comment_id not in [c["id"] for c in deleted_comments_log]:
                        deleted_comments_log.append({"id": comment_id, "text": text})

                save_stats()

    except Exception as e:
        print("fetch_and_moderate_comments exception:", e)

    return results

def _last_n_days(n=14):
    days = []
    today = datetime.utcnow().date()
    for i in range(n-1, -1, -1):
        d = today - timedelta(days=i)
        days.append(d.strftime("%Y-%m-%d"))
    return days

def get_report_stats():
    dates = _last_n_days(14)
    analyzed = []
    toxic = []
    deleted = []
    for d in dates:
        day = daily_counters.get(d, {"analyzed": 0, "toxic": 0, "deleted": 0})
        analyzed.append(day["analyzed"])
        toxic.append(day["toxic"])
        deleted.append(day["deleted"])

    top_words = [{"word": w, "count": c} for w, c in top_words_counter.most_common(12)]

    return {
        "totals": totals,
        "previewMode": PREVIEW_MODE,
        "threshold": TOXICITY_THRESHOLD,
        "topWords": top_words,
        "trend": {
            "dates": dates,
            "analyzed": analyzed,
            "toxic": toxic,
            "deleted": deleted
        }
    }