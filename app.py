import os
import time
from zoneinfo import ZoneInfo

import streamlit as st
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from database import Store, STATUSES, ConflictError

st.set_page_config(page_title="Surya Ghar · Team Quotations", page_icon="☀️", layout="wide")

def setting(name):
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name, "")
    except FileNotFoundError:
        return ""

@st.cache_resource
def connect(url, username, password):
    store = Store(url)
    store.initialize(username, password)
    return store

def local_time(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M:%S %p IST")

st.title("☀️ Surya Ghar quotations")
st.caption("One shared workspace for your team's quotations and agreements.")
if not setting("DATABASE_URL"):
    st.info("Connect your Render PostgreSQL database by setting DATABASE_URL in your hosting secrets. See README.md for setup.")
    st.stop()
try:
    store = connect(setting("DATABASE_URL"), setting("ADMIN_USERNAME"), setting("ADMIN_PASSWORD"))
except ValueError as exc:
    st.error(str(exc))
    st.stop()
except SQLAlchemyError:
    st.error("Unable to connect to the database. Check your DATABASE_URL and database availability in the hosting settings.")
    st.stop()

if "user" not in st.session_state:
    mode = st.radio("Welcome", ["Sign in", "Sign up"], horizontal=True)
    if mode == "Sign up":
        st.subheader("Join your team")
        st.caption("Create your member account with a username and password.")
        with st.form("signup", clear_on_submit=False):
            new_username = st.text_input("Choose a username (2–5 characters)", max_chars=5)
            new_password = st.text_input("Choose a password (at least 8 characters)", type="password")
            register = st.form_submit_button("Create account", type="primary")
        if register:
            try:
                store.add_user(new_username, new_password)
                st.success("Account created. Select Sign in above to log in.")
            except ValueError as exc:
                st.error(str(exc))
            except IntegrityError:
                st.error("That username is already taken. Choose another.")
            except SQLAlchemyError:
                st.error("Database unavailable. Please try again shortly.")
        st.stop()
    with st.form("login"):
        st.subheader("Team sign in")
        username = st.text_input("Username", max_chars=80)
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        if time.time() < st.session_state.get("login_retry", 0):
            st.error("Wait a few seconds before trying again.")
        else:
            try:
                user = store.login(username, password)
            except SQLAlchemyError:
                st.error("Database unavailable. Please try again shortly.")
                st.stop()
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.session_state.login_retry = time.time() + 3
                st.error("Incorrect username or password.")
    st.stop()

user = st.session_state.user
st.sidebar.write(f"Signed in as **{user['username']}**")
if st.sidebar.button("Sign out"):
    st.session_state.clear()
    st.rerun()
page = st.sidebar.radio("Workspace", ["Live quotations", "Create quotation", "Edit quotation"] + (["Team members"] if user["role"] == "admin" else []))

def fields(existing=None):
    existing = existing or {}
    col1, col2 = st.columns(2)
    with col1:
        number = st.text_input("Quotation number *", value=existing.get("number", ""), max_chars=80)
        customer = st.text_input("Customer name *", value=existing.get("customer", ""), max_chars=200)
        phone = st.text_input("Customer phone", value=existing.get("phone", ""), max_chars=30)
        address = st.text_area("Customer address", value=existing.get("address", ""))
    with col2:
        capacity = st.number_input("Solar capacity (kW) *", min_value=0.01, max_value=99999999.99, value=float(existing.get("capacity", 3.0)), step=0.1)
        amount = st.number_input("Quotation amount (₹) *", min_value=0.0, max_value=999999999999.99, value=float(existing.get("amount", 0)), step=1000.0)
        status = st.selectbox("Status", STATUSES, index=STATUSES.index(existing.get("status", "Draft")))
        notes = st.text_area("Notes / agreement details", value=existing.get("notes", ""))
    return dict(number=number, customer=customer, phone=phone, address=address, capacity=capacity, amount=amount, status=status, notes=notes)

def save(data, existing=None):
    try:
        quote_id = store.save(data, user["username"], existing["id"] if existing else None, existing["version"] if existing else None)
    except (ConflictError, ValueError) as exc:
        st.error(str(exc))
        return None
    except IntegrityError:
        st.error("That quotation number already exists. Open it from Edit quotation.")
        return None
    except SQLAlchemyError:
        st.error("Database unavailable. Your changes were not saved; please try again.")
        return None
    st.success("Quotation saved. Other members will see it on their live list within 5 seconds.")
    return quote_id

@st.fragment(run_every="5s")
def live_list():
    st.subheader("Live quotations")
    st.caption("Refreshes every 5 seconds while this page is open. Saved changes appear automatically.")
    query = st.text_input("Search quotation number, customer or phone").strip().lower()
    statuses = st.multiselect("Filter by status", STATUSES)
    try:
        rows = store.list_quotes()
    except SQLAlchemyError:
        st.error("Could not refresh quotations. Retrying automatically.")
        return
    a, b, c = st.columns(3)
    a.metric("Total quotations", len(rows))
    b.metric("Ongoing", sum(r["status"] not in ("Completed", "Cancelled") for r in rows))
    c.metric("Approved", sum(r["status"] == "Approved" for r in rows))
    filtered = [r for r in rows if (not statuses or r["status"] in statuses) and (not query or any(query in str(r[k]).lower() for k in ("number", "customer", "phone")))]
    if not filtered:
        st.info("No quotations found. Create a quotation to get started.")
        return
    st.dataframe([{"Quotation": r["number"], "Customer": r["customer"], "Phone": r["phone"], "Capacity (kW)": float(r["capacity"]), "Amount (₹)": float(r["amount"]), "Status": r["status"], "Updated by": r["updated_by"], "Updated at": local_time(r["updated_at"]), "Revision": r["version"]} for r in filtered], width='stretch', hide_index=True)

try:
    if page == "Live quotations":
        live_list()
    elif page == "Create quotation":
        st.subheader("Create quotation")
        with st.form("create", clear_on_submit=False):
            data = fields()
            submitted = st.form_submit_button("Save quotation", type="primary")
        if submitted:
            save(data)
    elif page == "Edit quotation":
        rows = store.list_quotes()
        if not rows:
            st.info("Create a quotation first.")
        else:
            lookup = {r["id"]: f"{r['number']} · {r['customer']}" for r in rows}
            selected = st.selectbox("Select a quotation (type to search)", list(lookup), format_func=lookup.get)
            if st.session_state.get("edit_id") != selected:
                st.session_state.edit_id = selected
                st.session_state.edit_snapshot = store.get_quote(selected)
            if st.button("Reload latest quotation", help="Replaces the form with the latest saved values; unsaved edits will be discarded."):
                st.session_state.edit_snapshot = store.get_quote(selected)
                st.rerun()
            existing = st.session_state.edit_snapshot
            st.caption(f"Editing revision {existing['version']} · Last saved by {existing['updated_by']} · {local_time(existing['updated_at'])}")
            @st.fragment(run_every="5s")
            def check_revision():
                try:
                    latest = store.get_quote(selected)
                    if latest["version"] != existing["version"]:
                        st.warning(f"A newer revision was saved by {latest['updated_by']}. Reload the latest quotation before saving.")
                except SQLAlchemyError:
                    st.warning("Unable to check for new changes right now.")
            check_revision()
            with st.form(f"edit_{selected}_{existing['version']}"):
                data = fields(existing)
                submitted = st.form_submit_button("Save changes", type="primary")
            if submitted:
                if save(data, existing) is not None:
                    st.session_state.edit_snapshot = store.get_quote(selected)
                    st.session_state.saved_notice = True
                    st.rerun()
            if st.session_state.pop("saved_notice", False):
                st.success("Changes saved.")
            with st.expander("Update history"):
                for item in store.get_history(selected):
                    st.markdown(f"**Revision {item['version']} · {item['actor']}** · {local_time(item['timestamp'])}")
                    st.text(item["details"])
    elif page == "Team members":
        st.subheader("Add a team member")
        with st.form("new_user", clear_on_submit=True):
            username = st.text_input("New username (2–5 characters)", max_chars=5)
            password = st.text_input("New password (at least 8 characters)", type="password")
            submitted = st.form_submit_button("Create member")
        if submitted:
            try:
                store.add_user(username, password)
                st.success("Member created. They can now sign in.")
            except ValueError as exc:
                st.error(str(exc))
            except IntegrityError:
                st.error("That username already exists.")
except SQLAlchemyError:
    st.error("Database unavailable. Please try again shortly.")
