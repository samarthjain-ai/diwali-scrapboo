YOUR YEAR, YOUR JOURNEY - DIWALI SCRAPBOOK  (by Samarth Jain (Subh))

RUN LOCALLY
    pip install -r requirements.txt
    streamlit run DAY_311.py

GO LIVE (free, ~5 minutes) - Streamlit Community Cloud
 1. Create a GitHub repo and upload everything in this folder (keep the folder structure,
    including .streamlit/, fonts/ and images/).
 2. Go to share.streamlit.io, sign in with GitHub, click "Create app".
 3. Pick the repo, branch "main", main file path: DAY_311.py, then Deploy.
 4. You get a link like https://yourname-diwali.streamlit.app - share it.

PERSONAL LINKS
    https://your-app.streamlit.app/?name=Riya   opens the scrapbook already addressed to Riya.

WHAT'S IN IT
 - Name form + balloons, festival-day banner (Dhanteras 6 Nov ... Bhai Dooj 11 Nov 2026)
 - Light a diya (9 diyas, the page glows warmer, balloons on the ninth)
 - Your year in three lines -> downloadable "My Year" card
 - Write on the paper -> downloadable note
 - One looping Diwali song (original instrumental, no licence issues). It has no off switch and starts
   on the visitor's first tap, because browsers block sound until the visitor interacts with the page.
   The file is static/diwali_ambient.mp3 (needs .streamlit/config.toml - keep it).
 - Wish wall: visitors pin wishes everyone can read. Saved in data/wishes.json while the app runs
   (Streamlit Cloud wipes it on restart/redeploy).
   To remove a wish: set a secret ADMIN_KEY (Streamlit Cloud: app Settings > Secrets, ADMIN_KEY = "yourpassword"),
   then open https://your-app/?admin=yourpassword - delete and backup/restore boxes appear under the wall.
   Download a backup before the event ends if you want to keep the wishes.

KEEP TOGETHER: DAY_311.py, style311.css, requirements.txt, images/, fonts/, static/, .streamlit/
