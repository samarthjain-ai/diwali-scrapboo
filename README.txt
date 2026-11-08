# 🪔 Your Year, Your Journey — Diwali Scrapbook

A Diwali scrapbook web app by **Samarth Jain (Subh)**, built with Python and Streamlit.

**🔗 Live app: https://diwali-scrapboo.streamlit.app/**

Greet someone by name by adding `?name=` to the link, for example
https://diwali-scrapboo.streamlit.app/?name=Riya

---

## What's in it

- **Opening:** name form, balloons, and a festival-day banner (Dhanteras 6 Nov, Choti Diwali 7 Nov, Diwali 8 Nov, Govardhan Puja 10 Nov, Bhai Dooj 11 Nov 2026).
- **Light a diya:** nine diyas to light; the page glows warmer with each one, and balloons fly on the ninth.
- **Your year:** three short prompts that make a downloadable "My Year" card.
- **Wish wall:** visitors pin a short wish that everyone can read.
- **A note to keep:** write on scrapbook paper and download it as a PNG.
- **Music:** one looping, original Diwali instrumental. It has no off switch and starts on the visitor's first tap, because browsers block sound until the visitor interacts with the page.

## Run it on your computer

```
pip install -r requirements.txt
streamlit run DAY_311.py
```

## Project files

| Path | What it is |
|---|---|
| `DAY_311.py` | The app |
| `style311.css` | Styling |
| `requirements.txt` | Python packages |
| `images/` | Scrapbook pictures and the blank paper |
| `fonts/` | Handwriting font (Kalam) used on the downloaded cards |
| `static/diwali_ambient.mp3` | The song |
| `.streamlit/config.toml` | Light theme and static file serving (needed for the music) |

Keep all of these together, and keep them at the top level of the repo.

## Deploy (free) on Streamlit Community Cloud

1. Put the project on GitHub, with the files at the top level of the repo.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **Create app**, choose the repo, branch `main`, and main file path `DAY_311.py`.
4. (Optional) In **Advanced settings → Secrets**, add `ADMIN_KEY = "choose-a-password"`.
5. Click **Deploy**.

Any change committed to GitHub redeploys the app automatically.

## Wish wall: things to know

- Wishes are saved in `data/wishes.json` while the app is running.
- On the free plan the app **sleeps after about 12 hours without visitors**. When it wakes up, or when it is redeployed, **the wall is cleared**.
- **Do not push changes while people are using the app.**
- Each visitor can pin up to 3 wishes, and wishes with links or emails are refused.

### Remove a wish or back up the wall

1. Set the secret `ADMIN_KEY` (Streamlit Cloud: app **Settings → Secrets**).
2. Open `https://diwali-scrapboo.streamlit.app/?admin=your-password`.
3. Under the wall you will see boxes to **delete a wish** and to **download or restore a backup**.

Download a backup before the event ends if you want to keep the wishes.

## Change the song

1. Get an MP3 you are allowed to use (royalty-free tracks from Pixabay Music or the YouTube Audio Library work well).
2. Rename it `diwali_ambient.mp3` and put it in `static/`, replacing the old file.
3. Commit to GitHub, then refresh the page with Ctrl+F5.

---

Made with ♡ by Samarth Jain (Subh) · Diwali Edition
