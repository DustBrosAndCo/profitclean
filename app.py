def edit_profile_page():
    if 'user' not in st.session_state:
        st.session_state.page = "login"
        st.rerun()
    st.markdown("### ✏️ Edit Your Profile")
    user_data = get_current_user_data()
    if not user_data:
        st.error("User not found")
        return
    uid, username, email, role, mgr_id, sup_id, hire_date, totp_enabled = user_data
    with st.form("edit_profile"):
        new_username = st.text_input("Username", username)
        new_email = st.text_input("Email", email)
        st.text_input("Role", role, disabled=True)
        st.text_input("Hire Date", hire_date[:10] if hire_date else "N/A", disabled=True)
        st.markdown("#### Change Password")
        cur_pwd = st.text_input("Current Password", type="password")
        new_pwd = st.text_input("New Password", type="password")
        confirm_pwd = st.text_input("Confirm New Password", type="password")
        st.markdown("#### Two‑Factor Authentication")
        if totp_enabled:
            st.success("2FA is ENABLED")
            if st.button("Disable 2FA"):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE users SET totp_enabled = 0, totp_secret = NULL WHERE id = ?", (uid,))
                conn.commit()
                conn.close()
                st.success("2FA disabled")
                st.rerun()
        else:
            st.info("2FA is disabled. You can enable it.")
            if st.button("Enable 2FA"):
                secret = generate_totp_secret()
                uri = get_totp_uri(secret, email)
                st.session_state.totp_secret = secret
                st.session_state.totp_email = email
                st.session_state.page = "setup_2fa"
                st.rerun()
        if st.form_submit_button("Save Changes"):
            updates = []
            params = []
            if new_username != username:
                updates.append("username = ?")
                params.append(new_username)
            if new_email != email:
                updates.append("email = ?")
                params.append(new_email)
            if new_pwd:
                # Verify current password
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT password_hash FROM users WHERE id = ?", (uid,))
                row = c.fetchone()
                conn.close()
                if not row or not verify_password(cur_pwd, row[0]):
                    st.error("Current password is incorrect")
                elif new_pwd != confirm_pwd:
                    st.error("New passwords do not match")
                else:
                    valid, msg = validate_password_strength(new_pwd)
                    if not valid:
                        st.error(msg)
                    else:
                        hashed, salt = hash_password(new_pwd)
                        updates.append("password_hash = ?")
                        updates.append("salt = ?")
                        params.extend([hashed, salt])
            if updates:
                params.append(uid)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
                conn.commit()
                conn.close()
                st.success("Profile updated")
                st.rerun()
    if st.button("\u2190 Back"):
        st.session_state.page = "dashboard"
        st.rerun()
