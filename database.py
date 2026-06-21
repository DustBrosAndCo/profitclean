import secrets
import sqlite3

from constants import DB_PATH


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")

    # Companies table
    c.execute('''CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subdomain TEXT UNIQUE,
        owner_id INTEGER,
        created_at DATETIME,
        is_active BOOLEAN DEFAULT 1,
        settings_json TEXT,
        timezone TEXT DEFAULT 'America/New_York',
        notification_email TEXT
    )''')

    # Users table (enhanced)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT DEFAULT 'worker',
        company_id INTEGER,
        manager_id INTEGER,
        supervisor_id INTEGER,
        can_manage_workers BOOLEAN DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        login_attempts INTEGER DEFAULT 0,
        locked_until DATETIME,
        hire_date DATETIME,
        last_raise_date DATETIME,
        raise_recommended_by INTEGER,
        raise_recommended_date DATETIME,
        totp_secret TEXT,
        totp_enabled INTEGER DEFAULT 0,
        backup_codes TEXT,
        created_at DATETIME,
        last_login DATETIME,
        created_ip TEXT,
        approval_status TEXT DEFAULT 'approved',
        approved_by INTEGER,
        approval_date DATETIME,
        invite_code TEXT,
        phone TEXT,
        address TEXT,
        emergency_contact TEXT,
        hourly_rate REAL,
        language TEXT DEFAULT 'en',
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (manager_id) REFERENCES users(id),
        FOREIGN KEY (supervisor_id) REFERENCES users(id),
        FOREIGN KEY (approved_by) REFERENCES users(id)
    )''')

    # Notifications table
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        company_id INTEGER,
        title TEXT,
        message TEXT,
        notification_type TEXT,
        related_id INTEGER,
        read_status INTEGER DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')

    # Estimate history/timeline
    c.execute('''CREATE TABLE IF NOT EXISTS estimate_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estimate_id INTEGER,
        status_from TEXT,
        status_to TEXT,
        changed_by INTEGER,
        notes TEXT,
        changed_at DATETIME,
        FOREIGN KEY (estimate_id) REFERENCES estimates(id),
        FOREIGN KEY (changed_by) REFERENCES users(id)
    )''')

    # Client communication log
    c.execute('''CREATE TABLE IF NOT EXISTS client_communications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        estimate_id INTEGER,
        communication_type TEXT,
        subject TEXT,
        message TEXT,
        sent_by INTEGER,
        sent_at DATETIME,
        FOREIGN KEY (client_id) REFERENCES clients(id),
        FOREIGN KEY (estimate_id) REFERENCES estimates(id),
        FOREIGN KEY (sent_by) REFERENCES users(id)
    )''')

    # Job templates
    c.execute('''CREATE TABLE IF NOT EXISTS job_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        name TEXT,
        description TEXT,
        property_type TEXT,
        estimated_hours REAL,
        task_list TEXT,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')

    # Worker availability
    c.execute('''CREATE TABLE IF NOT EXISTS worker_availability (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        available_date DATE,
        time_slots TEXT,
        is_available BOOLEAN DEFAULT 1,
        FOREIGN KEY (worker_id) REFERENCES users(id)
    )''')

    # Performance reviews
    c.execute('''CREATE TABLE IF NOT EXISTS performance_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        worker_id INTEGER,
        reviewer_id INTEGER,
        review_date DATETIME,
        rating INTEGER,
        feedback TEXT,
        goals TEXT,
        next_review_date DATE,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (worker_id) REFERENCES users(id),
        FOREIGN KEY (reviewer_id) REFERENCES users(id)
    )''')

    # Pending worker requests
    c.execute('''CREATE TABLE IF NOT EXISTS pending_workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password_hash TEXT,
        salt TEXT,
        requested_manager_email TEXT,
        company_id INTEGER,
        requested_at DATETIME,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')

    # Sessions
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_token TEXT UNIQUE NOT NULL,
        expires_at DATETIME,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Audit log
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        ip_address TEXT,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Global settings for market rates, tax, and pricing defaults
    c.execute('''CREATE TABLE IF NOT EXISTS global_settings (
        name TEXT PRIMARY KEY,
        value TEXT,
        updated_at DATETIME
    )''')

    # Business profile
    c.execute('''CREATE TABLE IF NOT EXISTS business_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER UNIQUE,
        business_name TEXT,
        phone TEXT,
        email TEXT,
        hourly_wage REAL,
        profit_target REAL,
        min_job_fee REAL,
        home_city TEXT,
        per_mile_rate REAL,
        sales_tax_rate REAL DEFAULT 0.06,
        monthly_rent REAL DEFAULT 0,
        monthly_insurance REAL DEFAULT 0,
        monthly_vehicles REAL DEFAULT 0,
        monthly_marketing REAL DEFAULT 0,
        monthly_software REAL DEFAULT 0,
        monthly_admin_salary REAL DEFAULT 0,
        desired_profit_margin REAL DEFAULT 0.20,
        smtp_email TEXT,
        smtp_password TEXT,
        smtp_server TEXT,
        smtp_port INTEGER DEFAULT 587,
        setup_complete INTEGER DEFAULT 0,
        logo_url TEXT,
        business_hours TEXT,
        cancellation_policy TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS company_integrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        integration_type TEXT NOT NULL,
        enabled INTEGER DEFAULT 0,
        access_token TEXT,
        refresh_token TEXT,
        token_expires DATETIME,
        settings TEXT,
        last_sync DATETIME,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        UNIQUE(company_id, integration_type)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS external_bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        integration_type TEXT NOT NULL,
        external_id TEXT,
        hashed_email TEXT,
        invitee_name TEXT,
        start_time DATETIME,
        end_time DATETIME,
        service_type TEXT,
        status TEXT,
        raw_questions TEXT,
        imported_at DATETIME,
        processed INTEGER DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS integration_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        integration_type TEXT,
        action TEXT,
        status TEXT,
        message TEXT,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')

    # Clients
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        business_name TEXT,
        contact_name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        zip TEXT,
        lat REAL,
        lon REAL,
        notes TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        preferred_contact_method TEXT DEFAULT 'email',
        lead_source TEXT,
        password_hash TEXT,
        salt TEXT,
        portal_enabled INTEGER DEFAULT 0,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Client portal access tokens (for clients to set up/reset their portal password)
    c.execute('''CREATE TABLE IF NOT EXISTS client_portal_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at DATETIME NOT NULL,
        used BOOLEAN DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')

    # Estimates
    c.execute('''CREATE TABLE IF NOT EXISTS estimates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        client_id INTEGER,
        client_name TEXT,
        client_email TEXT,
        city TEXT,
        property_type TEXT,
        square_feet REAL,
        bedrooms INTEGER DEFAULT 0,
        bathrooms INTEGER DEFAULT 0,
        frequency TEXT,
        complexity INTEGER,
        travel_miles REAL,
        toll_cost REAL,
        add_on_window REAL DEFAULT 0,
        add_on_carpet REAL DEFAULT 0,
        add_on_floor REAL DEFAULT 0,
        add_on_disinfection REAL DEFAULT 0,
        add_on_pressure REAL DEFAULT 0,
        add_on_trash REAL DEFAULT 0,
        add_on_event REAL DEFAULT 0,
        holiday_surcharge REAL DEFAULT 0,
        emergency_premium REAL DEFAULT 0,
        location_discount REAL DEFAULT 0,
        contract_discount REAL DEFAULT 0,
        subtotal REAL,
        tax REAL,
        estimated_price REAL,
        lowest_price REAL,
        fair_price REAL,
        highest_price REAL,
        sweet_spot_price REAL,
        created_at DATETIME,
        status TEXT DEFAULT 'draft',
        approved_at DATETIME,
        expires_at DATETIME,
        notes TEXT,
        follow_up_reminder DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')

    # Estimate approvals
    c.execute('''CREATE TABLE IF NOT EXISTS estimate_approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        estimate_id INTEGER,
        worker_id INTEGER,
        requested_price REAL,
        requested_at DATETIME,
        status TEXT DEFAULT 'pending',
        manager_id INTEGER,
        approved_at DATETIME,
        notes TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (estimate_id) REFERENCES estimates(id),
        FOREIGN KEY (worker_id) REFERENCES users(id),
        FOREIGN KEY (manager_id) REFERENCES users(id)
    )''')

    # Scheduled jobs
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        client_id INTEGER,
        client_name TEXT,
        client_email TEXT,
        estimate_id INTEGER,
        assigned_worker_id INTEGER,
        scheduled_date DATE,
        scheduled_time TEXT,
        status TEXT DEFAULT 'scheduled',
        reminder_sent INTEGER DEFAULT 0,
        completed_at DATETIME,
        notes TEXT,
        job_template_id INTEGER,
        actual_hours REAL,
        actual_cost REAL,
        client_signature TEXT,
        photos_before TEXT,
        photos_after TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (client_id) REFERENCES clients(id),
        FOREIGN KEY (assigned_worker_id) REFERENCES users(id),
        FOREIGN KEY (job_template_id) REFERENCES job_templates(id)
    )''')

    # Job assignments
    c.execute('''CREATE TABLE IF NOT EXISTS job_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        worker_id INTEGER,
        assigned_by INTEGER,
        assigned_at DATETIME,
        status TEXT DEFAULT 'assigned',
        travel_distance REAL,
        completed_at DATETIME,
        notes TEXT,
        FOREIGN KEY (worker_id) REFERENCES users(id),
        FOREIGN KEY (assigned_by) REFERENCES users(id)
    )''')

    # Inspections
    c.execute('''CREATE TABLE IF NOT EXISTS inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        client_id INTEGER,
        client_name TEXT,
        property_type TEXT,
        scheduled_job_id INTEGER,
        areas_json TEXT,
        inspection_data TEXT,
        status TEXT DEFAULT 'in_progress',
        started_at DATETIME,
        completed_at DATETIME,
        photos TEXT,
        recommendations TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')

    # Quick jobs
    c.execute('''CREATE TABLE IF NOT EXISTS quick_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        job_date DATE,
        description TEXT,
        hours REAL,
        amount_invoiced REAL,
        job_expenses REAL,
        profit REAL,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Monthly expenses
    c.execute('''CREATE TABLE IF NOT EXISTS monthly_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        month_year TEXT,
        insurance REAL DEFAULT 0,
        vehicle REAL DEFAULT 0,
        software REAL DEFAULT 0,
        advertising REAL DEFAULT 0,
        other REAL DEFAULT 0,
        notes TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Team chat
    c.execute('''CREATE TABLE IF NOT EXISTS team_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        username TEXT,
        user_role TEXT,
        message TEXT,
        channel TEXT DEFAULT 'general',
        is_private BOOLEAN DEFAULT 0,
        recipient_id INTEGER,
        read_status INTEGER DEFAULT 0,
        created_at DATETIME,
        attachments TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Supplies
    c.execute('''CREATE TABLE IF NOT EXISTS supplies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        name TEXT,
        category TEXT,
        unit TEXT,
        current_stock REAL,
        reorder_level REAL,
        unit_cost REAL,
        last_updated DATETIME,
        supplier TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Supply usage
    c.execute('''CREATE TABLE IF NOT EXISTS supply_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        supply_id INTEGER,
        job_id INTEGER,
        quantity_used REAL,
        used_by INTEGER,
        used_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (supply_id) REFERENCES supplies(id),
        FOREIGN KEY (used_by) REFERENCES users(id)
    )''')

    # Worker certifications
    c.execute('''CREATE TABLE IF NOT EXISTS worker_certifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        worker_id INTEGER,
        certification_name TEXT,
        issuing_body TEXT,
        date_earned DATE,
        expiration_date DATE,
        certificate_file_path TEXT,
        notes TEXT,
        verified_by INTEGER,
        verified_at DATETIME,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (worker_id) REFERENCES users(id),
        FOREIGN KEY (verified_by) REFERENCES users(id)
    )''')

    # Worker badges
    c.execute('''CREATE TABLE IF NOT EXISTS worker_badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        worker_id INTEGER,
        badge_name TEXT,
        badge_icon TEXT,
        earned_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (worker_id) REFERENCES users(id)
    )''')

    # Support tickets
    c.execute('''CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        ticket_id TEXT UNIQUE,
        user_id INTEGER,
        user_email TEXT,
        issue_type TEXT,
        description TEXT,
        steps_to_reproduce TEXT,
        screenshot TEXT,
        status TEXT DEFAULT 'open',
        priority TEXT DEFAULT 'normal',
        assigned_to INTEGER,
        created_at DATETIME,
        updated_at DATETIME,
        resolved_at DATETIME,
        resolution_notes TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (assigned_to) REFERENCES users(id)
    )''')

    # Support messages
    c.execute('''CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        ticket_id INTEGER,
        user_id INTEGER,
        message TEXT,
        is_staff BOOLEAN DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (ticket_id) REFERENCES support_tickets(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Email templates
    c.execute('''CREATE TABLE IF NOT EXISTS email_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        name TEXT,
        subject TEXT,
        body TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME,
        UNIQUE(company_id, name),
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')

    # Error logs
    c.execute('''CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        error_type TEXT,
        error_message TEXT,
        page_url TEXT,
        stack_trace TEXT,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Worker transfers
    c.execute('''CREATE TABLE IF NOT EXISTS worker_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        from_company_id INTEGER,
        to_company_id INTEGER,
        transferred_by INTEGER,
        transferred_at DATETIME,
        reason TEXT,
        FOREIGN KEY (worker_id) REFERENCES users(id),
        FOREIGN KEY (from_company_id) REFERENCES companies(id),
        FOREIGN KEY (to_company_id) REFERENCES companies(id),
        FOREIGN KEY (transferred_by) REFERENCES users(id)
    )''')

    # System health logs
    c.execute('''CREATE TABLE IF NOT EXISTS system_health (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_name TEXT,
        metric_value TEXT,
        recorded_at DATETIME
    )''')

    # Bulk actions history
    c.execute('''CREATE TABLE IF NOT EXISTS bulk_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_type TEXT,
        affected_company_ids TEXT,
        affected_user_ids TEXT,
        performed_by INTEGER,
        performed_at DATETIME,
        details TEXT,
        FOREIGN KEY (performed_by) REFERENCES users(id)
    )''')

    # Approval requests for role-based permissions
    c.execute('''CREATE TABLE IF NOT EXISTS approval_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        requester_id INTEGER NOT NULL,
        request_type TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        current_value TEXT,
        requested_value TEXT,
        reason TEXT,
        status TEXT DEFAULT 'pending',
        admin_notes TEXT,
        created_at DATETIME,
        reviewed_at DATETIME,
        reviewed_by INTEGER,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (requester_id) REFERENCES users(id),
        FOREIGN KEY (reviewed_by) REFERENCES users(id)
    )''')

    # Activity log for worker actions
    c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target_type TEXT,
        target_id INTEGER,
        details TEXT,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Authentication logs for security tracking
    c.execute('''CREATE TABLE IF NOT EXISTS auth_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        email TEXT,
        event_type TEXT NOT NULL,
        status TEXT,
        ip_address TEXT,
        user_agent TEXT,
        error_message TEXT,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Password reset tokens
    c.execute('''CREATE TABLE IF NOT EXISTS password_reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        verification_code TEXT,
        expires_at DATETIME NOT NULL,
        used BOOLEAN DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Estimate approval tokens
    c.execute('''CREATE TABLE IF NOT EXISTS estimate_approval_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estimate_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at DATETIME NOT NULL,
        used BOOLEAN DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY (estimate_id) REFERENCES estimates(id),
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')

    # Indexes for the columns most frequently filtered on (tenant scoping by
    # company_id, foreign-key joins, and the login lookup).
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users(lower(email))")
    c.execute("CREATE INDEX IF NOT EXISTS idx_clients_user ON clients(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_estimates_company ON estimates(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_estimates_client ON estimates(client_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_company ON scheduled_jobs(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_worker ON scheduled_jobs(assigned_worker_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_client ON scheduled_jobs(client_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_job_assignments_job ON job_assignments(job_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_job_assignments_worker ON job_assignments(worker_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_quick_jobs_company ON quick_jobs(company_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, read_status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id)")

    conn.commit()
    conn.close()


def migrate_database():
    """Add missing columns to existing database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check if invite_code column exists in users table
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    
    # Add invite_code column if it doesn't exist
    if 'invite_code' not in columns:
        try:
            c.execute("ALTER TABLE users ADD COLUMN invite_code TEXT")
            print("Added invite_code column to users table")
        except sqlite3.OperationalError as e:
            print(f"Could not add invite_code: {e}")
    
    # Generate invite codes for existing users
    try:
        c.execute("SELECT id FROM users WHERE invite_code IS NULL OR invite_code = ''")
        users_without_code = c.fetchall()
        for user in users_without_code:
            invite_code = secrets.token_hex(4).upper()
            c.execute("UPDATE users SET invite_code = ? WHERE id = ?", (invite_code, user[0]))
        print(f"Generated invite codes for {len(users_without_code)} users")
    except Exception as e:
        print(f"Error generating invite codes: {e}")
    
    conn.commit()
    conn.close()

    # Email template uniqueness migration
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_templates'")
    if c.fetchone():
        c.execute("PRAGMA table_info(email_templates)")
        existing_cols = [row[1] for row in c.fetchall()]
        if 'is_active' not in existing_cols:
            try:
                c.execute("ALTER TABLE email_templates ADD COLUMN is_active BOOLEAN DEFAULT 1")
                print('Added is_active column to email_templates')
            except sqlite3.OperationalError as e:
                print(f"Could not add is_active column: {e}")
        if 'created_at' not in existing_cols:
            try:
                c.execute("ALTER TABLE email_templates ADD COLUMN created_at DATETIME")
                print('Added created_at column to email_templates')
            except sqlite3.OperationalError as e:
                print(f"Could not add created_at column: {e}")

        c.execute('''
            DELETE FROM email_templates
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM email_templates
                GROUP BY company_id, name
            )
        ''')
        try:
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_email_templates_company_name ON email_templates(company_id, name)")
        except sqlite3.OperationalError as e:
            print(f"Could not create unique index for email_templates: {e}")
    conn.commit()
    conn.close()
    
    # Worker badges migration
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='worker_badges'")
    if c.fetchone():
        c.execute("PRAGMA table_info(worker_badges)")
        existing_cols = [row[1] for row in c.fetchall()]
        if 'company_id' not in existing_cols:
            try:
                c.execute("ALTER TABLE worker_badges ADD COLUMN company_id INTEGER")
                print('Added company_id column to worker_badges')
                c.execute("""
                    UPDATE worker_badges
                    SET company_id = (SELECT company_id FROM users WHERE users.id = worker_badges.worker_id)
                """)
                print('Populated company_id for existing worker_badges')
            except sqlite3.OperationalError as e:
                print(f"Could not add company_id column to worker_badges: {e}")
        if 'badge_icon' not in existing_cols:
            try:
                c.execute("ALTER TABLE worker_badges ADD COLUMN badge_icon TEXT")
                print('Added badge_icon column to worker_badges')
            except sqlite3.OperationalError as e:
                print(f"Could not add badge_icon column to worker_badges: {e}")
    conn.commit()
    conn.close()

    # Ensure integration tables exist for older databases and add missing company_integrations columns
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='company_integrations'")
    if not c.fetchone():
        c.execute('''CREATE TABLE IF NOT EXISTS company_integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            integration_type TEXT NOT NULL,
            enabled INTEGER DEFAULT 0,
            access_token TEXT,
            refresh_token TEXT,
            token_expires DATETIME,
            settings TEXT,
            last_sync DATETIME,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            UNIQUE(company_id, integration_type)
        )''')
        print('Created company_integrations table')

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='external_bookings'")
    if not c.fetchone():
        c.execute('''CREATE TABLE IF NOT EXISTS external_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            integration_type TEXT NOT NULL,
            external_id TEXT,
            hashed_email TEXT,
            invitee_name TEXT,
            start_time DATETIME,
            end_time DATETIME,
            service_type TEXT,
            status TEXT,
            raw_questions TEXT,
            imported_at DATETIME,
            processed INTEGER DEFAULT 0,
            created_at DATETIME,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )''')
        print('Created external_bookings table')

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='integration_logs'")
    if not c.fetchone():
        c.execute('''CREATE TABLE IF NOT EXISTS integration_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            integration_type TEXT,
            action TEXT,
            status TEXT,
            message TEXT,
            created_at DATETIME,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )''')
        print('Created integration_logs table')

    c.execute("PRAGMA table_info(company_integrations)")
    existing_columns = [row[1] for row in c.fetchall()]
    if 'token_expires' not in existing_columns:
        try:
            c.execute("ALTER TABLE company_integrations ADD COLUMN token_expires DATETIME")
            print('Added token_expires column to company_integrations')
        except sqlite3.OperationalError:
            pass
    if 'settings' not in existing_columns:
        try:
            c.execute("ALTER TABLE company_integrations ADD COLUMN settings TEXT")
            print('Added settings column to company_integrations')
        except sqlite3.OperationalError:
            pass
    if 'last_sync' not in existing_columns:
        try:
            c.execute("ALTER TABLE company_integrations ADD COLUMN last_sync DATETIME")
            print('Added last_sync column to company_integrations')
        except sqlite3.OperationalError:
            pass
    if 'updated_at' not in existing_columns:
        try:
            c.execute("ALTER TABLE company_integrations ADD COLUMN updated_at DATETIME")
            print('Added updated_at column to company_integrations')
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

    # Client portal password migration
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(clients)")
    client_columns = [col[1] for col in c.fetchall()]
    for col_name, col_def in [("password_hash", "TEXT"), ("salt", "TEXT"), ("portal_enabled", "INTEGER DEFAULT 0")]:
        if col_name not in client_columns:
            try:
                c.execute(f"ALTER TABLE clients ADD COLUMN {col_name} {col_def}")
                print(f"Added {col_name} column to clients")
            except sqlite3.OperationalError:
                pass

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='client_portal_tokens'")
    if not c.fetchone():
        c.execute('''CREATE TABLE IF NOT EXISTS client_portal_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            expires_at DATETIME NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at DATETIME,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )''')
        print('Created client_portal_tokens table')

    # Enforce email uniqueness within a company (does not affect cross-company
    # collisions, which authenticate_client disambiguates by password).
    try:
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_company_email
            ON clients(company_id, email)
            WHERE email IS NOT NULL AND email != ''
        """)
    except sqlite3.OperationalError as e:
        print(f"Could not create unique index on clients(company_id, email) - likely existing duplicates: {e}")

    conn.commit()
    conn.close()

    # Language preference migration
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    user_columns = [col[1] for col in c.fetchall()]
    if 'language' not in user_columns:
        try:
            c.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'en'")
            print("Added language column to users")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
