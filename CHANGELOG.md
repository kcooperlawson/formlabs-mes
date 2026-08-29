### 🛠️ Formlabs MES Development Log
*Detailed tracking of architectural, database, and UI/UX deployments.*

---
**v3.6.0 - Saturday, Aug 29, 2026 (Security, Performance & Architectural Refactor)**
* **Bcrypt Cryptographic Migration:** Completely stripped legacy raw SHA-256 hashing and implemented industry-standard `bcrypt` across the entire application. Integrated automated salting mechanisms into user creation, password updates, and authentication pipelines to defend against dictionary attacks.
* **Database Monolith Decoupling:** Successfully dismantled the 1,000+ line `database.py` monolith into a highly modular, four-pillar architecture:
  * `db_core.py`: Isolated SQLAlchemy engine, session definitions, and database URL bindings.
  * `models.py`: Extracted all declarative base classes and table schemas into a dedicated object layer.
  * `crud.py`: Centralized all Create, Read, Update, and Delete operations and SQL querying logic.
  * `utils.py`: Segregated operating system interactions, directory generation, and database backup routines.
* **Facade Pattern Routing Hub:** Engineered the legacy `database.py` file into a lightweight import routing hub. This completely shielded the front-end `pages/` directory from the structural refactor, ensuring zero broken imports across the UI.
* **Zero-Latency UI (Thread-Blocking Elimination):** Conducted a global codebase sweep to eliminate all synchronous `time.sleep()` calls that were actively freezing the server thread for concurrent users. 
* **Optimized Session Loops:** Rewrote the "Double-Take" auto-login loop, explicit logout sequence, and theme selection functions to utilize instant `st.rerun()` triggers, drastically speeding up module-to-module navigation.
* **Asynchronous UX Notifications:** Replaced blocking form-submission success messages with asynchronous `st.toast()` notifications, allowing the application to reload instantly while gracefully persisting success messages across the rerun state.
* **Execution Order Optimization:** Repaired critical application boot sequences by hoisting baseline catalog constants above seed functions and relocating database initialization calls (`init_db`) to the absolute end of the application load cycle.
* **Emergency Admin Utility:** Engineered a standalone `create_admin.py` terminal script equipped with `.env` injection. This provides a permanent developer backdoor to force-provision securely hashed superuser accounts in the event of a system lockout or a total database wipe.

**v3.5.1 - Friday, Aug 28, 2026 (Pre-Auth Theming & Session Hardening)**
* **Pre-Authentication Theme Engine:** Built a collapsible theme selector on the login screen that saves to browser cookies and injects custom CSS instantly upon page load, prior to authentication.
* **Session Hardening & Auto-Login Fix:** Resolved the phantom auto-login loop ("zombie cookies") by introducing a Hard Lockout flag (`logged_out=true`), capturing and preserving user aesthetics during the session memory wipe.
* **Universal UI Parity:** Standardized the navigation router, sidebar profiles, "Account & Preferences" modal, and embedded Release Notes reader across all sub-modules to eliminate layout rendering bugs.
* **Branding & Authorization:** Added explicit `st.logo()` bindings to the headers and expanded authorization gates to grant IT Administrators full hardware management capabilities alongside plant managers.

**v3.5.0 - Thursday, Aug 27, 2026 (Admin Plant Configuration & Navigation Refactor)**
* **Global Navigation & Role Routing:** Refactored the primary entry file structure, optimized sidebar utilities, and engineered a "God Mode" role-based framework that dynamically renders accessible modules based on user authorization.
* **IT Admin Console & Fleet Management:** Implemented a dedicated suite for provisioning users, executing disaster recovery, and managing physical reactor assets, station endpoints, and plant parameters in a unified view.
* **Session Resilience & Security:** Enclosed token revocation routines in exception-handling blocks, implemented asynchronous token validation to survive hard browser refreshes, and added a Superuser Debug Mode for management.
* **Unified User Experience:** Consolidated account settings, dynamic CSS typography scaling, profile avatars, global feedback inboxes, and the system changelog into a standardized interface.
* **Analytics & External Sync:** Restored sidebar visibility in the Analytics module, transitioned Plotly charts to adaptive RGBA layouts, and integrated custom payload filtering for Google Cloud Sheet webhooks.

**v3.4.0 - Wednesday, Aug 26, 2026 (OpSec Hardening & Dynamic Spec Engine)**
* **OpSec & Confidentiality:** Extracted proprietary material formulations from source code into encrypted database storage to prevent repository data leaks.
* **Resin Canvas CRUD:** Built complete administrative data controls to manage custom material specifications directly within the database layer.
* **Slidable Tab Selector:** Custom-styled interface tabs into touch-optimized, horizontally scrollable pill controls.
* **Theme Architecture & Code Cleanup:** Centralized global layout styling properties into a core shared stylesheet, resolved navigation glitches, and scrubbed developer controls from production views.

**v3.3.0 - Wednesday, Aug 26, 2026 (Security, Routing & UX)**
* **Universal State Management & Security:** Enforced strict server-side authorization gates across all sub-modules and implemented token-based authentication persistence to prevent unauthorized direct URL access.
* **UI/UX Refactoring:** Extracted user settings into a responsive sidebar drawer and optimized layout responsiveness/toggle controls for tablet and mobile viewports.
* **Dynamic Data Routing:** Upgraded external webhooks with dynamic multi-destination payload routing to segregate summary metrics from raw audit streams safely.
* **DevOps Hardening:** Extracted PII, database URIs, webhooks, and SMTP credentials into secure environment configuration files.

**v3.2.0 - Tuesday, Aug 25, 2026 (Compliance & Advanced Reconciliation)**
* **Compliance Hard Gates:** Implemented mandatory pre-shift validation checklists, locking operational modules until compliance verification is completed.
* **Advanced Tank Reconciliation:** Enhanced vessel calibration algorithms to accept precise volume inputs, automatically adjusting digital inventory levels and logging system reconciliations.
* **Roster Flexibility & Controls:** Added mid-shift role reassignment utilities and built administrative record management with cascading recalculations to maintain accurate completion metrics.
* **Disaster Recovery:** Integrated one-click database backup and disaster recovery utilities directly within administrative control views.

**v3.1.0 - Monday, Aug 24, 2026 (Design System & Intelligence)**
* **Nexus Analytics Hub & Pace Engine:** Built a centralized dashboard featuring downtime Pareto analysis, operator heatmaps, and real-time shift trajectory modeling to calculate projected output.
* **Dynamic CSS Engine:** Deployed a multi-theme design system featuring responsive layout controls, hover transitions, and dynamic active indicators.
* **Automated PDF Reporting:** Developed an automated shift handover document generator with email distribution pipelines.
* **Floor Comms:** Implemented a real-time messaging interface for direct communication between plant leadership and floor personnel.

**v3.0.0 - Sunday, Aug 23, 2026 (The Foundation)**
* **Architecture:** Migrated core data persistence layer to an ORM framework backed by relational database infrastructure.
* **Core Modules:** Established baseline routing architecture for workstation, management, and telemetry modules.
* **Blob Storage:** Configured secure media storage handling for station cleanliness audits and incident attachments.