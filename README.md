# Surya Ghar team quotations

Streamlit app with a shared PostgreSQL database, individual member logins, quotation forms, searchable live list, update history and conflict protection.

## Run locally

Use Python 3.11 or newer. Install dependencies:

```powershell
python -m pip install -r requirements.txt
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` privately. Put your Render **external** PostgreSQL URL into `DATABASE_URL`, choose `ADMIN_USERNAME`, and set `ADMIN_PASSWORD` to a unique password of at least 8 characters. Never commit the secrets file.

```powershell
python -m streamlit run app.py
```

The app automatically creates three tables prefixed `sg_` and the first administrator. Sign in and use **Team members** to create individual accounts. Changing the bootstrap password in hosting settings does not change an existing administrator's password.

## Deploy on Render

1. Push these files to your own GitHub repository, excluding secrets.
2. Create a Render **Web Service** connected to that repository, using the Python runtime. Select the same region as your PostgreSQL database.
3. Build command: `pip install -r requirements.txt`
4. Start command: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true`
5. In the service's Environment settings, add `DATABASE_URL` with your existing database's **internal URL**, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` (8 or more characters).
6. Deploy, open the service URL, sign in and create your team accounts.

For Streamlit Community Cloud or another host outside Render, use the **external URL** instead. Supply the three settings in that host's secrets configuration. Do not paste database passwords into chats or commit them to GitHub.

## Deploy on Streamlit Community Cloud

Connect your GitHub account at https://share.streamlit.io/ and select this repository, branch `main`, and entrypoint `app.py`. Choose Python 3.12 or newer. In Advanced settings → Secrets, add `DATABASE_URL` using your Render external URL (with `?sslmode=require&connect_timeout=10`), `ADMIN_USERNAME`, and `ADMIN_PASSWORD`. Keep these values out of the repository. Deploy and use the shared app URL for all members.

## Team workflow

Create a quotation with number, customer name, phone, address, solar capacity, amount, status and notes. The quotation number is unique and normalized to uppercase. The live list fetches saved updates every 5 seconds while open. Forms do not broadcast keystrokes: changes become visible after Save.

Each edit loads a fixed revision. Saving uses an atomic revision check. If another member saved first, your save is rejected and your entered values remain visible. Copy any changes you want to retain, then use **Reload latest quotation** and reapply them. Record updates and audit history are committed in the same database transaction.

All timestamps display in India Standard Time. All members can edit all quotations. Administrators can create member accounts. Members can also select **Sign up** before signing in and register with only a username and password. Anyone who can access the app can register and receive access to the shared quotations. Signup always creates a member account, never an administrator. The app tracks quotation records; it does not generate PDF agreements, calculate government subsidies or submit applications to government portals.

## Validation

```powershell
python -m unittest discover -s tests -v
```

Tests use an in-memory SQLite database to verify validation, account login, duplicate numbers, history and stale-edit rejection. Actual PostgreSQL connectivity and multi-browser refresh must be verified after setting hosting secrets.

Official references: [Streamlit fragments](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment), [Render PostgreSQL connections](https://render.com/docs/postgresql-creating-connecting).
