import base64
import datetime as dt
import html
import json
import os
import random
import threading
import time
import uuid
from io import BytesIO
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="Your Year, Your Journey | Diwali",
    page_icon="🪔",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "images"

QUOTES = [
    "You do not have to see the whole staircase. Just take the first step.",
    "Small steps every day create journeys worth remembering.",
    "Let your courage be louder than your doubts.",
    "The light you are looking for may already be within you.",
    "Grow through what you go through.",
    "A new beginning is simply a chance to write a better story.",
]

SENDER = "Samarth Jain (Subh)"
MAX_DIYAS = 9
MUSIC_FILE = Path(__file__).resolve().parent / "static" / "diwali_ambient.mp3"  # served at /app/static/

# Diwali 2026 (India): Dhanteras 6 Nov, Choti Diwali 7 Nov, Lakshmi Puja 8 Nov,
# Govardhan Puja 10 Nov, Bhai Dooj 11 Nov.
FESTIVAL_DAYS = {
    (11, 6): ("Happy Dhanteras", "The festival of lights begins today. May your home fill with prosperity."),
    (11, 7): ("Happy Choti Diwali", "A little light tonight, a lot of light tomorrow."),
    (11, 8): ("Happy Diwali", "Today is Lakshmi Puja. Light a diya and make a wish."),
    (11, 10): ("Happy Govardhan Puja", "Gratitude, food and family. A beautiful day."),
    (11, 11): ("Happy Bhai Dooj", "To siblings, near and far. Here's to your bond."),
}


def festival_today():
    try:
        from zoneinfo import ZoneInfo
        today = dt.datetime.now(ZoneInfo("Asia/Kolkata")).date()
    except Exception:
        today = dt.date.today()
    if today.year == 2026:
        return FESTIVAL_DAYS.get((today.month, today.day))
    return None


# ---------- WISH WALL STORAGE ----------
# One shared list for everybody visiting the running app, saved to data/wishes.json.
# (On Streamlit Community Cloud the file is wiped when the app restarts or is redeployed.)
WISH_FILE = Path(__file__).resolve().parent / "data" / "wishes.json"
MAX_WISH_LEN = 140
MAX_WISHES_PER_SESSION = 3
SEED_WISHES = [
    {
        "id": "seed1",
        "name": SENDER,
        "text": "Happy Deepavali! May every diya you light today bring a little more joy into your year.",
        "ts": 0,
    }
]


@st.cache_resource
def wish_store() -> dict:
    wishes = None
    try:
        wishes = json.loads(WISH_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"lock": threading.Lock(), "wishes": wishes if isinstance(wishes, list) else list(SEED_WISHES)}


def _persist(store: dict) -> None:
    try:
        WISH_FILE.parent.mkdir(exist_ok=True)
        tmp = WISH_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(store["wishes"], ensure_ascii=False), encoding="utf-8")
        tmp.replace(WISH_FILE)
    except Exception:
        pass  # keep running from memory if the disk is read-only


def add_wish(name: str, text: str) -> None:
    store = wish_store()
    with store["lock"]:
        store["wishes"].insert(0, {"id": uuid.uuid4().hex, "name": name, "text": text, "ts": int(time.time())})
        del store["wishes"][200:]
        _persist(store)


def delete_wish(wish_id: str) -> None:
    store = wish_store()
    with store["lock"]:
        store["wishes"] = [w for w in store["wishes"] if w["id"] != wish_id]
        _persist(store)


def is_admin() -> bool:
    key = os.environ.get("ADMIN_KEY", "")
    if not key:
        try:
            key = str(st.secrets.get("ADMIN_KEY", ""))
        except Exception:
            key = ""
    return bool(key) and st.query_params.get("admin", "") == key


def check_wish(text: str) -> str:
    """Return an error message, or "" if the wish is fine to post."""
    lowered = text.lower()
    if len(text) < 3:
        return "Write a few words for your wish first."
    if any(bit in lowered for bit in ("http", "www.", ".com", ".in/", "@")):
        return "Please keep links and emails off the wall."
    if st.session_state.get("wishes_posted", 0) >= MAX_WISHES_PER_SESSION:
        return f"You've pinned {MAX_WISHES_PER_SESSION} wishes already. Thank you!"
    return ""


# ---------- SESSION STATE ----------
if "visitor_name" not in st.session_state:
    st.session_state.visitor_name = ""

# Personal links: https://your-app/?name=Riya opens the scrapbook already addressed to Riya.
if not st.session_state.visitor_name:
    _qp_name = st.query_params.get("name", "")
    if isinstance(_qp_name, list):
        _qp_name = _qp_name[0] if _qp_name else ""
    st.session_state.visitor_name = _qp_name.strip()[:40]

if "diyas" not in st.session_state:
    st.session_state.diyas = 0

if "quote" not in st.session_state:
    st.session_state.quote = random.choice(QUOTES)

# ---------- LOAD CSS ----------
css_path = BASE_DIR / "style311.css"
if css_path.exists():
    st.markdown(
        f"<style>{css_path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )

# ---------- HELPERS ----------
def section_label(number: str, label: str) -> None:
    st.markdown(
        f'<div class="section-kicker"><span>{number}</span><span>{label}</span></div>',
        unsafe_allow_html=True,
    )


# The writing area on quote_paper.jpg, as fractions of the image (left, top, right, bottom).
# The on-screen editor in the final section uses the same box, so what you type is what you download.
PAPER_BOX = (0.25, 0.19, 0.82, 0.80)
FONT_PATH = BASE_DIR / "fonts" / "Kalam-Regular.ttf"  # handwriting font, also covers Hindi


def _load_font(size: int):
    for candidate in (FONT_PATH, "DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"):
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int) -> list:
    """Wrap text, keeping the visitor's line breaks and splitting over-long words."""
    lines = []
    for paragraph in text.replace("\r", "").split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = ""
            for char in word:  # a single word wider than the paper: break by character
                if draw.textlength(current + char, font=font) <= max_width:
                    current += char
                else:
                    lines.append(current)
                    current = char
        lines.append(current)
    return lines


def create_note_card(message: str, author: str) -> bytes:
    """Write a visitor's message onto the supplied blank scrapbook-paper image."""
    paper_path = IMAGE_DIR / "quote_paper.jpg"
    if not paper_path.exists():
        raise FileNotFoundError(f"Missing scrapbook paper image: {paper_path}")

    # Kalam has Latin + Devanagari but no emoji; drop them rather than print empty boxes.
    message = "".join(ch for ch in message if ord(ch) < 0x10000)

    image = Image.open(paper_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    W, H = image.size
    left, top, right, bottom = (W * PAPER_BOX[0], H * PAPER_BOX[1], W * PAPER_BOX[2], H * PAPER_BOX[3])
    box_w, box_h = int(right - left), int(bottom - top)

    # Start at the same relative size as the on-screen editor, shrink only if the message needs it.
    size = max(16, round(W * 0.042))
    author_room = int(H * 0.05)
    while True:
        font = _load_font(size)
        lines = _wrap(draw, message, font, box_w)
        line_h = int(size * 1.6)
        if len(lines) * line_h <= box_h - author_room or size <= 16:
            break
        size -= 2

    ink = "#49332E"
    y = top
    for line in lines:
        width = draw.textlength(line, font=font)
        draw.text((left + (box_w - width) / 2, y), line, fill=ink, font=font)
        y += line_h

    small = _load_font(max(16, round(W * 0.032)))
    author_text = f"— {author}" if author else "— A little note to remember"
    aw = draw.textlength(author_text, font=small)
    draw.text((left + (box_w - aw) / 2, min(y + line_h * 0.4, bottom - author_room * 0.2)),
              author_text, fill="#806657", font=small)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def create_year_card(name: str, items: list) -> bytes:
    """Draw the 'My Year' keepsake: a title plus the answers the visitor filled in."""
    image = Image.open(IMAGE_DIR / "quote_paper.jpg").convert("RGB")
    draw = ImageDraw.Draw(image)
    W, H = image.size
    left, top = W * PAPER_BOX[0], H * PAPER_BOX[1]
    box_w, box_h = int(W * (PAPER_BOX[2] - PAPER_BOX[0])), int(H * (PAPER_BOX[3] - PAPER_BOX[1]))

    def clean(text):
        return "".join(ch for ch in text if ord(ch) < 0x10000).strip()

    title = f"{clean(name)}'s Year" if clean(name) else "My Year"
    items = [(label, clean(text)) for label, text in items if clean(text)]

    size = max(16, round(W * 0.040))
    while True:
        title_font, body_font, label_font = _load_font(round(size * 1.35)), _load_font(size), _load_font(max(12, round(size * 0.62)))
        blocks = [(title_font, [title], "#7D394B", round(size * 0.9))]
        for label, text in items:
            blocks.append((label_font, [label.upper()], "#B77C3E", round(size * 0.2)))
            blocks.append((body_font, _wrap(draw, text, body_font, box_w), "#49332E", round(size * 0.9)))
        total = sum(int(f.size * 1.5) * len(lines) + gap for f, lines, _, gap in blocks)
        if total <= box_h or size <= 16:
            break
        size -= 2

    y = top
    for font, lines, colour, gap in blocks:
        for line in lines:
            draw.text((left + (box_w - draw.textlength(line, font=font)) / 2, y), line, fill=colour, font=font)
            y += int(font.size * 1.5)
        y += gap

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


# ---------- TOP NAVIGATION ----------
st.markdown(
    """
    <nav class="top-nav">
      <div class="brand">✦ A little light, a little magic</div>
      <div class="nav-links">
        <a href="#celebration">Celebration</a>
        <a href="#journey">Your journey</a>
        <a href="#little-reminders">Reminders</a>
        <a href="#diya">Diya</a>
        <a href="#my-year">Your year</a>
        <a href="#wish-wall">Wish wall</a>
        <a href="#final-wish">Your note</a>
      </div>
    </nav>
    """,
    unsafe_allow_html=True,
)

# One small script, injected into the page itself (not left in the helper iframe, which Streamlit may rebuild):
#  1. nav links scroll explicitly (Streamlit scrolls inside its own container and can ignore #links)
#  2. the single Diwali song loops quietly and starts on the visitor's first tap/key press
#     (browsers do not allow sound before the visitor has interacted with the page)
PAGE_JS = """
(function () {
  if (window.__diwaliInit) return;
  window.__diwaliInit = true;

  function goTo(id) {
    var target = document.getElementById(id);
    if (!target) return;
    target.scrollIntoView({ block: "start" });
    // images and fonts finishing loading can shift the page; re-check a few times
    [300, 800, 1800].forEach(function (ms) {
      setTimeout(function () {
        if (Math.abs(target.getBoundingClientRect().top - 90) > 8) target.scrollIntoView({ block: "start" });
      }, ms);
    });
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('.top-nav a[href^="#"]');
    if (!a) return;
    e.preventDefault();
    e.stopPropagation();
    goTo(a.getAttribute("href").slice(1));
  }, true);

  var audio = new Audio("__SRC__");
  audio.loop = true;
  audio.volume = 0.45;
  window.__diwaliAudio = audio;
  var events = ["pointerdown", "keydown", "touchstart"];
  function stop() { events.forEach(function (ev) { document.removeEventListener(ev, start, true); }); }
  function start() { audio.play().then(stop).catch(function () {}); }
  events.forEach(function (ev) { document.addEventListener(ev, start, true); });
  start();
})();
"""

_music_src = "/app/static/diwali_ambient.mp3" if MUSIC_FILE.exists() else ""
_page_js = PAGE_JS.replace("__SRC__", _music_src)
try:
    st.html("<script>" + _page_js + "</script>", unsafe_allow_javascript=True)
except TypeError:  # older Streamlit: the iframe route below does the job
    pass
components.html(
    "<script>"
    "var d = window.parent.document;"
    "if (!d.getElementById('diwali-js')) {"
    "  var s = d.createElement('script'); s.id = 'diwali-js';"
    "  s.textContent = " + json.dumps(_page_js) + ";"
    "  d.head.appendChild(s);"
    "}"
    "</script>",
    height=0,
)

if st.session_state.pop("scroll_top", False):
    # Back to the very top after "Make a new scrapbook" (the unique comment makes the browser run it every time)
    components.html(
        "<script>/*" + str(time.time()) + "*/"
        "var w = window.parent;"
        "function go() { var m = w.document.querySelector('[data-testid=\"stMain\"]');"
        " if (m) m.scrollTo({ top: 0 }); w.scrollTo(0, 0); }"
        "go(); setTimeout(go, 250); setTimeout(go, 700);</script>",
        height=0,
    )
    st.toast("A fresh scrapbook is ready ✨")

_festival = festival_today()
if _festival:
    st.markdown(
        f'<div class="festival-banner"><b>🪔 {_festival[0]}!</b> {_festival[1]}</div>',
        unsafe_allow_html=True,
    )

# ---------- INTRO / NAME ENTRY ----------
intro_left, intro_right = st.columns(
    [1, 1], gap="large", vertical_alignment="center"
)

with intro_left:
    st.markdown(
        """
        <section class="intro intro-side" id="top">
          <div class="intro-eyebrow">A DIWALI SCRAPBOOK · A NEW BEGINNING</div>
          <h1>Light up your<br/><em>journey.</em></h1>
          <p class="intro-copy">
            A little celebration of who you are, how far you've come,
            and all the beautiful things still waiting for you.
          </p>
          <div class="intro-flourish">✧　🪔　✧</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    with st.form("name_form"):
        entered_name = st.text_input(
            "FIRST, WHAT SHOULD WE CALL YOU?",
            value=st.session_state.visitor_name,
            placeholder="Write your name here...",
            label_visibility="visible",
        )
        submitted = st.form_submit_button(
            "Open my scrapbook ✨", width="stretch"
        )
        if submitted:
            if entered_name.strip():
                st.session_state.visitor_name = entered_name.strip()[:40]
                st.session_state.celebrate = True
                st.rerun()
            else:
                st.warning("Add your name to open your Diwali scrapbook.")

with intro_right:
    opening_image = IMAGE_DIR / "opening_scrapbook.jpg"
    if opening_image.exists():
        st.image(str(opening_image), width="stretch")
    else:
        st.warning("Add opening_scrapbook.jpg to the images folder.")

if st.session_state.pop("celebrate", False):
    st.balloons()

name = (
    html.escape(st.session_state.visitor_name)
    if st.session_state.visitor_name
    else "beautiful soul"
)

if not st.session_state.visitor_name:
    st.markdown(
        '<p class="hint-line">Enter your name to personalise your scrapbook. You can still explore below.</p>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="scroll-cue">SCROLL TO EXPLORE <span>↓</span></div>',
    unsafe_allow_html=True,
)

# ---------- CELEBRATION ----------
st.markdown('<div id="celebration"></div>', unsafe_allow_html=True)
section_label("01", "THE CELEBRATION")

left, right = st.columns([1.05, 0.95], gap="large", vertical_alignment="center")
with left:
    st.markdown(
        f"""
        <div class="celebration-copy">
          <div class="handwritten-small">A note just for you</div>
          <h2>Happy<br/><em>Deepavali,</em><br/>{name}!</h2>
          <p>May your home be filled with light, your heart with joy,
          and your life with endless blessings.</p>
          <div class="signature">With warmth &amp; good wishes ♡<br/>— Samarth Jain (Subh)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with right:
    diwali_image = IMAGE_DIR / "diwali_reference.jpg"
    if diwali_image.exists():
        st.image(str(diwali_image), width="stretch")
    else:
        st.markdown(
            '<div class="image-placeholder">Place your Diwali image at <code>images/diwali_reference.jpg</code></div>',
            unsafe_allow_html=True,
        )

st.markdown(
    """
    <div class="divider-ornament">✿　✧　✿</div>
    <div class="center-quote">
      “May the festival of lights bring happiness, prosperity<br/>
      and new beginnings to you and your loved ones.”
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- JOURNEY ----------
st.markdown('<div id="journey"></div>', unsafe_allow_html=True)
section_label("02", "YOUR JOURNEY AHEAD")
st.markdown(
    f"""
    <div class="section-heading">
      <h2>Every new light<br/><em>begins somewhere.</em></h2>
      <p>{name}, wherever the coming year takes you, make room for the things that help you grow.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

journey_visuals = st.columns(2, gap="large")
with journey_visuals[0]:
    st.image(str(IMAGE_DIR / "journey_train.jpg"), width="stretch")
    st.markdown(
        '<p class="image-caption">Some journeys are about enjoying the way.</p>',
        unsafe_allow_html=True,
    )
with journey_visuals[1]:
    st.image(str(IMAGE_DIR / "journey_map.jpg"), width="stretch")
    st.markdown(
        '<p class="image-caption">Stay curious. There is always more to discover.</p>',
        unsafe_allow_html=True,
    )

journey_cols = st.columns(3, gap="medium")
journey_cards = [
    ("01", "Growth", "Keep learning. Keep becoming. Your progress does not need to look like anyone else's.", "✿"),
    ("02", "Courage", "Take the first step even when the whole path is not clear yet.", "♡"),
    ("03", "Joy", "Notice the little things. A peaceful moment is also a beautiful achievement.", "☼"),
    ("04", "Possibility", "Stay curious. Some of life's best chapters begin with an unexpected opportunity.", "✧"),
    ("05", "Patience", "Give your dreams time, and give yourself kindness while you work towards them.", "❀"),
    ("06", "Purpose", "Choose what matters to you, then show up for it with consistency.", "🪔"),
]
for index, (number, title, body, symbol) in enumerate(journey_cards):
    with journey_cols[index % 3]:
        st.markdown(
            f"""
            <div class="journey-card">
              <div class="card-top"><span>{number}</span><span>{symbol}</span></div>
              <h3>{title}</h3>
              <p>{body}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------- REMINDERS / QUOTES ----------
st.markdown('<div id="little-reminders"></div>', unsafe_allow_html=True)
section_label("03", "LITTLE REMINDERS")
quote_left, quote_right = st.columns([0.9, 1.1], gap="large", vertical_alignment="center")
with quote_left:
    st.markdown(
        """
        <div class="quote-intro">
          <div class="handwritten-small">Keep this close</div>
          <h2>A few words<br/><em>for the road.</em></h2>
          <p>Save a thought that feels right for this chapter of your life.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with quote_right:
    quote_images = st.columns(2, gap="small")
    with quote_images[0]:
        st.image(str(IMAGE_DIR / "vintage_quote.jpg"), width="stretch")
    with quote_images[1]:
        st.image(str(IMAGE_DIR / "flower_reminder.jpg"), width="stretch")
    st.markdown(
        f'<div class="quote-paper"><div class="quote-mark">“</div>'
        f'<p>{html.escape(st.session_state.quote)}</p>'
        f'<div class="quote-bottom">A REMINDER FOR {name.upper()}</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("Find another little reminder ↻", width="stretch"):
        choices = QUOTES
        alternatives = [quote for quote in choices if quote != st.session_state.quote]
        st.session_state.quote = random.choice(alternatives)
        st.rerun()

# ---------- LIGHT A DIYA ----------
def light_diya() -> None:
    if st.session_state.diyas < MAX_DIYAS:
        st.session_state.diyas += 1
        if st.session_state.diyas == MAX_DIYAS:
            st.session_state.celebrate = True


st.markdown('<div id="diya"></div>', unsafe_allow_html=True)
section_label("04", "LIGHT A DIYA")
lit = st.session_state.diyas
st.markdown(
    f"""
    <div class="section-heading">
      <h2>One light<br/><em>at a time.</em></h2>
      <p>Tap to light a diya, {name}. Light all nine and watch the room glow.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
if lit:
    glow = 40 + lit * 22
    alpha = 0.10 + lit * 0.035
    st.markdown(
        f"<style>.stApp::after{{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;"
        f"box-shadow:inset 0 0 {glow}px rgba(255,160,50,{alpha:.2f});transition:all .6s ease}}</style>",
        unsafe_allow_html=True,
    )
lamps = "".join(
    f'<span class="diya{" lit" if i < lit else ""}" style="animation-delay:{i * 0.2:.1f}s">🪔</span>'
    for i in range(MAX_DIYAS)
)
if lit == 0:
    diya_note = "Your first diya is waiting."
elif lit < MAX_DIYAS:
    diya_note = f"{lit} of {MAX_DIYAS} diyas lit."
else:
    diya_note = f"All {MAX_DIYAS} lit. May your year glow just as bright, {name}!"
st.markdown(
    f'<div class="diya-row">{lamps}</div><p class="diya-note">{diya_note}</p>',
    unsafe_allow_html=True,
)
_, diya_mid, _ = st.columns([1, 1, 1])
with diya_mid:
    st.button(
        "Light a diya 🪔" if lit < MAX_DIYAS else "All lit ✨",
        on_click=light_diya,
        disabled=lit >= MAX_DIYAS,
        width="stretch",
        key="light_diya_btn",
    )

# ---------- YOUR YEAR IN REVIEW ----------
st.markdown('<div id="my-year"></div>', unsafe_allow_html=True)
section_label("05", "YOUR YEAR")
st.markdown(
    """
    <div class="section-heading">
      <h2>Your year,<br/><em>in three lines.</em></h2>
      <p>Answer any of these and take home a one-page keepsake of your year.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
year_win = st.text_input("ONE THING I'M PROUD OF THIS YEAR", max_chars=90, key="year_win")
year_learned = st.text_input("ONE THING I LEARNED", max_chars=90, key="year_learned")
year_goal = st.text_input("ONE GOAL FOR NEXT YEAR", max_chars=90, key="year_goal")
if any(v.strip() for v in (year_win, year_learned, year_goal)):
    st.download_button(
        "Download My Year ✨",
        data=create_year_card(
            st.session_state.visitor_name,
            [("Proud of", year_win), ("Learned", year_learned), ("Next year", year_goal)],
        ),
        file_name="my_year.png",
        mime="image/png",
        width="stretch",
    )

# ---------- WISH WALL ----------
st.markdown('<div id="wish-wall"></div>', unsafe_allow_html=True)
section_label("06", "THE WISH WALL")
st.markdown(
    """
    <div class="section-heading">
      <h2>Pin a wish<br/><em>for everyone.</em></h2>
      <p>Leave a short Diwali wish. It appears on the wall for every visitor to read.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("wish_form", clear_on_submit=True):
    wish_name = st.text_input("YOUR NAME", value=st.session_state.visitor_name, max_chars=30)
    wish_text = st.text_area(
        "YOUR WISH", placeholder="May this year bring you...", max_chars=MAX_WISH_LEN, height=90
    )
    pinned = st.form_submit_button("Pin my wish 📌", width="stretch")
if pinned:
    problem = check_wish(wish_text.strip())
    if problem:
        st.warning(problem)
    else:
        add_wish(wish_name.strip() or "A friend", wish_text.strip())
        st.session_state.wishes_posted = st.session_state.get("wishes_posted", 0) + 1
        st.toast("Your wish is on the wall 📌")


@st.fragment(run_every=15)
def wish_wall() -> None:
    store = wish_store()
    with store["lock"]:
        wishes = list(store["wishes"][:30])
    notes = "".join(
        f'<div class="wish-note c{i % 4}"><p>{html.escape(w["text"])}</p>'
        f'<div class="wish-name">— {html.escape(w["name"])}</div></div>'
        for i, w in enumerate(wishes)
    )
    st.markdown(f'<div class="wall">{notes}</div>', unsafe_allow_html=True)
    st.caption(f"{len(store['wishes'])} wishes on the wall · updates automatically")
    if is_admin() and wishes:
        with st.expander("Admin: remove a wish"):
            labels = {f'{w["name"]}: {w["text"][:50]}': w["id"] for w in wishes}
            choice = st.selectbox("Wish", list(labels), key="admin_wish")
            if st.button("Delete this wish", key="admin_delete"):
                delete_wish(labels[choice])
                st.rerun()
    if is_admin():
        with st.expander("Admin: back up / restore the wall"):
            st.download_button(
                "Download backup (wishes.json)",
                data=json.dumps(store["wishes"], ensure_ascii=False, indent=1),
                file_name="wishes.json",
                mime="application/json",
                key="admin_backup",
            )
            restore = st.file_uploader("Restore from a backup", type="json", key="admin_restore")
            if restore is not None and st.button("Restore now", key="admin_restore_btn"):
                try:
                    data = json.loads(restore.getvalue().decode("utf-8"))
                    clean = [
                        {"id": str(w["id"]), "name": str(w["name"])[:30], "text": str(w["text"])[:MAX_WISH_LEN], "ts": int(w.get("ts", 0))}
                        for w in data
                    ]
                    with store["lock"]:
                        store["wishes"] = clean[:200]
                        _persist(store)
                    st.rerun()
                except Exception:
                    st.error("That file is not a valid wishes backup.")


wish_wall()

# ---------- VISITOR'S PERSONAL NOTE ----------
st.markdown('<div id="final-wish"></div>', unsafe_allow_html=True)
section_label("07", "A LITTLE NOTE TO KEEP")
st.markdown(
    """
    <div class="section-heading personal-note-heading">
      <h2>A note to<br/><em>your future self.</em></h2>
      <p>Write a wish, a promise, a dream, or anything you want to remember.
      Your words will become a little scrapbook keepsake.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------- PERSONAL SCRAPBOOK WRITING ----------
paper_path = IMAGE_DIR / "quote_paper.jpg"

st.markdown(
    '<p class="paper-label">WRITE YOUR HEART OUT ♡</p>',
    unsafe_allow_html=True,
)

@st.cache_data
def paper_data_uri() -> str:
    return "data:image/jpeg;base64," + base64.b64encode(paper_path.read_bytes()).decode("utf-8")


# The editor is the paper itself: same aspect ratio as the image (no stretching), and everything
# inside is sized in cqw (1% of the paper's width) so the text scales with the paper.
# The padding below is PAPER_BOX expressed in cqw for a 736 x 1308 image.
pl, pt = PAPER_BOX[0] * 100, PAPER_BOX[1] * 100 * (1308 / 736)
pr = (1 - PAPER_BOX[2]) * 100
th = (PAPER_BOX[3] - PAPER_BOX[1]) * 100 * (1308 / 736)

st.markdown(
    f"""
    <style>
    .st-key-paper_editor {{
        background-image: url("{paper_data_uri()}");
        background-size: 100% 100%;
        background-repeat: no-repeat;
        width: min(100%, 560px) !important;
        aspect-ratio: 736 / 1308;
        align-self: center;
        container-type: inline-size;
        gap: 0;
        border-radius: 6px;
        box-shadow: 10px 12px 0 rgba(123,73,63,.15);
        overflow: hidden;
    }}

    /* cqw refers to an ancestor container, so the offsets live on the child, not on the paper itself */
    .st-key-paper_editor > [data-testid="stElementContainer"] {{
        margin: {pt:.2f}cqw {pr:.2f}cqw 0 {pl:.2f}cqw;
        width: auto !important;
    }}

    /* Strip every Streamlit/BaseWeb box (dark in dark mode) so the text sits on the paper itself */
    .st-key-paper_editor [data-testid="stTextArea"],
    .st-key-paper_editor [data-testid="stTextAreaRootElement"],
    .st-key-paper_editor [data-baseweb="textarea"],
    .st-key-paper_editor [data-baseweb="base-input"],
    .st-key-paper_editor [data-baseweb="textarea"] > div {{
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }}

    .st-key-paper_editor textarea {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        color: #49332E !important;
        -webkit-text-fill-color: #49332E !important;
        caret-color: #7d394b;
        font-family: 'Kalam', 'Segoe Print', cursive !important;
        font-size: 4.2cqw !important;
        line-height: 1.6 !important;
        text-align: center !important;
        resize: none !important;
        height: {th:.2f}cqw !important;
        min-height: 0 !important;
        padding: 0 !important;
    }}

    .st-key-paper_editor textarea::placeholder {{
        color: #8A7664 !important;
        -webkit-text-fill-color: #8A7664 !important;
        opacity: .75;
    }}

    /* tiny "0/350" counter: keep it quiet and on the paper */
    .st-key-paper_editor [data-testid="InputInstructions"] {{
        color: #8A7664 !important;
        background: transparent !important;
        font-size: 2.6cqw;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="paper_editor"):
    visitor_message = st.text_area(
        "Your message",
        placeholder="Dear future me,\n\nWrite your dreams, wishes and promises here...",
        height=200,
        max_chars=350,
        label_visibility="collapsed",
        key="visitor_message",
    )

if visitor_message.strip():
    note_image = create_note_card(
        visitor_message.strip(),
        st.session_state.visitor_name
    )

    st.download_button(
        label="Download My Scrapbook Note ♡",
        data=note_image,
        file_name="my_diary_note.png",
        mime="image/png",
        width="stretch",
    )

    

# ---------- FINAL WISH ----------
st.markdown(
    f"""
    <div class="final-wish">
      <div class="final-lamp">🪔</div>
      <div class="handwritten-small">Before you go...</div>
      <h2>Keep shining,<br/><em>{name}.</em></h2>
      <p>Your story is still being written. May the year ahead bring
      you meaningful moments, kind people, brave beginnings and
      reasons to be proud of how far you've come.</p>
      <div class="final-signoff">Happy Deepavali ♡</div>
      <div class="final-from">With love, Samarth Jain (Subh)</div>
      <div class="final-stars">✧　✿　✧　🪔　✧</div>
    </div>
    """,
    unsafe_allow_html=True,
)

def reset_scrapbook() -> None:
    # Runs as a button callback, i.e. before the widgets are created, so session_state may be edited.
    st.session_state.visitor_name = ""
    st.session_state.quote = random.choice(QUOTES)
    st.session_state.visitor_message = ""
    st.session_state.diyas = 0
    st.session_state.scroll_top = True
    for key in ("year_win", "year_learned", "year_goal"):
        st.session_state[key] = ""


_, mid, _ = st.columns([1, 1, 1])
with mid:
    st.button("Make a new scrapbook ↻", on_click=reset_scrapbook, width="stretch")

st.markdown(
    '<div class="footer">Made with ♡ by Samarth Jain (Subh) · Diwali Edition</div>',
    unsafe_allow_html=True,
)

