"""Small, dependency-free text helpers for the insights: keywords, mood and language guesses.

These are deliberately simple word-list heuristics. They are good enough to describe
a few hundred comments or a transcript in aggregate, not to judge a single sentence.
"""
import re
from collections import Counter

WORD_RE = re.compile(r"[^\W\d_][\w'’-]*", re.UNICODE)

STOPWORDS = set("""
a about above after again against all also am an and any are aren't as at be because been before being below
between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each few
for from further get got had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself
him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself just let's like me more most
mustn't my myself no nor not now of off on once only or other ought our ours ourselves out over own really same
shan't she she'd she'll she's should shouldn't so some such than that that's the their theirs them themselves then
there there's these they they'd they'll they're they've this those through to too under until up very was wasn't
we we'd we'll we're we've were weren't what what's when when's where where's which while who who's whom why why's
will with won't would wouldn't you you'd you'll you're you've your yours yourself yourselves yeah yes okay ok oh
gonna wanna gotta one two also even still much many well back know think going go make made way thing things
want see look right say said time people really actually video videos guys hey lol im dont thats ive youre
something anything everything every always never ever thank thanks please let us
""".split())

POSITIVE = set("""
love loved loving lovely awesome amazing great good best better beautiful brilliant cool excellent fantastic
favorite favourite fun funny glad happy helpful incredible inspiring legend legendary masterpiece nice perfect
recommend respect super thank thanks useful wonderful wow goat fire underrated informative clear enjoyed enjoy
appreciate appreciated hilarious genius blessed proud gem banger classic iconic epic
""".split())
NEGATIVE = set("""
awful bad boring clickbait cringe disappointed disappointing dislike fake hate hated horrible annoying lame
misleading poor sad scam stupid terrible trash waste worst wrong ugly useless overrated unsubscribe unsubscribed
garbage pathetic rubbish broken confusing lies liar
""".split())
POSITIVE_EMOJI = set("❤😍🥰😂🤣🔥👏👍💯🙌😊🥳💖💕✨🫶😁😄")
NEGATIVE_EMOJI = set("👎😡🤮😒😤💩😢😭🙄")
NEGATORS = {"not", "no", "never", "dont", "don't", "isn't", "wasn't", "didn't", "nothing"}

# Script ranges -> language for non-Latin text
SCRIPTS = [
    ("hi", re.compile(r"[ऀ-ॿ]")),   # Devanagari (Hindi, Marathi, Nepali)
    ("bn", re.compile(r"[ঀ-৿]")),
    ("ta", re.compile(r"[஀-௿]")),
    ("te", re.compile(r"[ఀ-౿]")),
    ("ar", re.compile(r"[؀-ۿ]")),   # Arabic script (also Urdu/Persian)
    ("ru", re.compile(r"[Ѐ-ӿ]")),   # Cyrillic
    ("ja", re.compile(r"[぀-ヿ]")),   # Kana
    ("ko", re.compile(r"[가-힯]")),
    ("zh", re.compile(r"[一-鿿]")),
    ("th", re.compile(r"[฀-๿]")),
    ("el", re.compile(r"[Ͱ-Ͽ]")),
    ("he", re.compile(r"[֐-׿]")),
]

# Very common function words per Latin-script language
LATIN_MARKERS = {
    "en": "the and is you this that it was for are with have just what so".split(),
    "es": "que el la los las es por para con una muy pero esto como más".split(),
    "pt": "que não muito uma com isso está você para mais é eu meu".split(),
    "fr": "le la les est et une pour pas que c'est très des je vous".split(),
    "de": "und ich das ist nicht die der es ein sehr auch mit".split(),
    "it": "che di non il è la per una sono molto questo anche".split(),
    "id": "yang dan ini itu tidak aku saya ada dengan bang banget juga".split(),
    "tr": "bir ve bu çok için ama ne da de gibi var".split(),
    "vi": "của là và có không này một những được người".split(),
    "tl": "ang ng mga sa po naman talaga ito ako ko".split(),
    # Hindi/Urdu written in Latin letters ("Hinglish")
    "hi-latn": "hai bhai nahi kya bhi aur yaar hain mein kuch sir bahut accha".split(),
}

LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "pt": "Portuguese", "fr": "French", "de": "German", "it": "Italian",
    "id": "Indonesian", "tr": "Turkish", "vi": "Vietnamese", "tl": "Filipino", "hi": "Hindi",
    "hi-latn": "Hindi (in English letters)", "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "ar": "Arabic / Urdu",
    "ru": "Russian / Cyrillic", "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "th": "Thai", "el": "Greek",
    "he": "Hebrew",
}

# Where speakers of each language mostly watch from (used for audience *hints* only)
LANGUAGE_COUNTRIES = {
    "en": ["United States", "India", "United Kingdom", "Philippines", "Canada"],
    "es": ["Mexico", "Spain", "Argentina", "Colombia", "United States"],
    "pt": ["Brazil", "Portugal"],
    "fr": ["France", "Canada", "Belgium", "Morocco"],
    "de": ["Germany", "Austria", "Switzerland"],
    "it": ["Italy"],
    "id": ["Indonesia"],
    "tr": ["Turkey"],
    "vi": ["Vietnam"],
    "tl": ["Philippines"],
    "hi": ["India"],
    "hi-latn": ["India", "Pakistan"],
    "bn": ["Bangladesh", "India"],
    "ta": ["India", "Sri Lanka"],
    "te": ["India"],
    "ar": ["Egypt", "Saudi Arabia", "Pakistan", "Iraq"],
    "ru": ["Russia", "Ukraine", "Kazakhstan"],
    "ja": ["Japan"],
    "ko": ["South Korea"],
    "zh": ["Taiwan", "Hong Kong", "Singapore"],
    "th": ["Thailand"],
    "el": ["Greece"],
    "he": ["Israel"],
}


def words(text):
    return [w.lower().strip("'’-") for w in WORD_RE.findall(text or "")]


def top_keywords(texts, limit=12, exclude=()):
    """Most frequent meaningful words across texts (each text counts a word once)."""
    exclude = {w.lower() for w in exclude}
    counts = Counter()
    for text in texts:
        counts.update({w for w in words(text) if len(w) > 3 and w not in STOPWORDS and w not in exclude})
    return [{"word": w, "count": c} for w, c in counts.most_common(limit) if c > 1 or len(texts) == 1]


def sentiment(text):
    """+1 positive, -1 negative, 0 neutral."""
    tokens = words(text)
    score = 0
    for i, w in enumerate(tokens):
        polarity = 1 if w in POSITIVE else -1 if w in NEGATIVE else 0
        if polarity and i and tokens[i - 1] in NEGATORS:
            polarity = -polarity
        score += polarity
    score += sum(1 for ch in text or "" if ch in POSITIVE_EMOJI)
    score -= sum(1 for ch in text or "" if ch in NEGATIVE_EMOJI)
    return 1 if score > 0 else -1 if score < 0 else 0


def detect_language(text):
    """Best-guess language code for a short text, or None if unclear."""
    if not text:
        return None
    for code, pattern in SCRIPTS:
        if len(pattern.findall(text)) >= 2:
            return code
    tokens = set(words(text))
    if not tokens:
        return None
    best, best_hits = None, 0
    for code, markers in LATIN_MARKERS.items():
        hits = sum(1 for m in markers if m in tokens)
        if hits > best_hits:
            best, best_hits = code, hits
    return best if best_hits >= 1 else None
