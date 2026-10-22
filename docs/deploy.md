# Putting the Observatory online (free, ~10 minutes)

The repository already holds everything the app needs: the built website
(`app/static/site/`) and the data (`data/`). Render runs it for free.

1. Go to https://render.com and sign up with your GitHub account.
2. **New → Blueprint**, pick `ChelseyMiguel/maui-climate-resilience-observatory`.
   Render reads `render.yaml` and creates the service `maui-climate-observatory`.
3. Click **Apply**. The first build takes a few minutes. Your link is shown at the
   top, like `https://maui-climate-observatory.onrender.com`.
4. Open the link and check: Overview, Map Explorer, 3D View, Analysis.

Notes
- The free plan sleeps after ~15 minutes without visitors; the first visit after
  that takes ~30–60 s to wake up. Open it yourself a minute before judging or a demo.
- `render.yaml` deploys the branch `claude/modest-hamilton-wy93h5`. After you merge
  into `main`, change `branch:` to `main`.
- GLOBE photos come live from api.globe.gov; if that is slow, the rest still works.
- Put the link in your CAC submission and video description.

Run it on your own computer instead: `./run.sh`, then open http://localhost:8000.
