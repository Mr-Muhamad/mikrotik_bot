"""Tests for deprecated migration functions and create_indexes in database/models.py."""

import warnings
from unittest.mock import patch


class TestCreateIndexes:
    def test_create_indexes_executes_without_error(self):
        from database.models import create_indexes

        create_indexes()

    def test_create_indexes_is_idempotent(self):
        from database.models import create_indexes

        create_indexes()
        create_indexes()

    def test_logs_admin_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_logs_admin",),
            )
            assert cursor.fetchone() is not None

    def test_logs_timestamp_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_logs_timestamp",),
            )
            assert cursor.fetchone() is not None

    def test_routers_active_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_routers_active",),
            )
            assert cursor.fetchone() is not None

    def test_routers_ip_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_routers_ip",),
            )
            assert cursor.fetchone() is not None

    def test_sessions_user_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_sessions_user",),
            )
            assert cursor.fetchone() is not None

    def test_backup_jobs_router_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_backup_jobs_router",),
            )
            assert cursor.fetchone() is not None

    def test_backup_jobs_created_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_backup_jobs_created",),
            )
            assert cursor.fetchone() is not None

    def test_health_router_time_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_health_router_time",),
            )
            assert cursor.fetchone() is not None

    def test_snapshots_router_date_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_snapshots_router_date",),
            )
            assert cursor.fetchone() is not None

    def test_tracked_messages_chat_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_tracked_messages_chat",),
            )
            assert cursor.fetchone() is not None

    def test_tracked_messages_date_index_exists(self):
        from database.models import create_indexes, get_db

        create_indexes()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                ("idx_tracked_messages_date",),
            )
            assert cursor.fetchone() is not None

    def test_all_expected_index_count(self):
        from database.models import create_indexes, get_db

        create_indexes()
        expected = {
            "idx_logs_admin",
            "idx_logs_timestamp",
            "idx_routers_active",
            "idx_routers_ip",
            "idx_sessions_user",
            "idx_backup_jobs_router",
            "idx_backup_jobs_created",
            "idx_health_router_time",
            "idx_snapshots_router_date",
            "idx_tracked_messages_chat",
            "idx_tracked_messages_date",
        }
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            )
            actual = {row["name"] for row in cursor.fetchall()}
        assert expected.issubset(actual)


class TestMigratePasswords:
    def test_emits_deprecation_warning(self):
        from database.models import migrate_passwords

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            migrate_passwords()
            deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecations) >= 1
            assert "deprecated" in str(deprecations[0].message).lower()

    def test_encrypts_plaintext_password(self):
        from database.models import get_db, migrate_passwords

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO discovered_routers (ip_address, password, is_active) VALUES (?, ?, ?)",
                ("10.99.0.1", "mysecretpass", 1),
            )
            conn.commit()

        migrate_passwords()

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT password FROM discovered_routers WHERE ip_address = ?",
                ("10.99.0.1",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["password"] == "enc_mysecretpass"

    def test_skips_already_encrypted_password(self):
        from database.models import get_db, migrate_passwords

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO discovered_routers (ip_address, password, is_active) VALUES (?, ?, ?)",
                ("10.99.0.2", "gAAAAAfake_token", 1),
            )
            conn.commit()

        migrate_passwords()

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT password FROM discovered_routers WHERE ip_address = ?",
                ("10.99.0.2",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["password"] == "gAAAAAfake_token"

    def test_skips_empty_password(self):
        from database.models import get_db, migrate_passwords

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO discovered_routers (ip_address, password, is_active) VALUES (?, ?, ?)",
                ("10.99.0.3", "", 1),
            )
            conn.commit()

        migrate_passwords()

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT password FROM discovered_routers WHERE ip_address = ?",
                ("10.99.0.3",),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["password"] == ""

    def test_mixed_password_states(self):
        from database.models import get_db, migrate_passwords

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO discovered_routers (ip_address, password, is_active) VALUES (?, ?, ?)",
                ("10.99.0.10", "plain1", 1),
            )
            cursor.execute(
                "INSERT INTO discovered_routers (ip_address, password, is_active) VALUES (?, ?, ?)",
                ("10.99.0.11", "gAAAAAalready_enc", 1),
            )
            cursor.execute(
                "INSERT INTO discovered_routers (ip_address, password, is_active) VALUES (?, ?, ?)",
                ("10.99.0.12", "plain2", 1),
            )
            conn.commit()

        migrate_passwords()

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ip_address, password FROM discovered_routers ORDER BY ip_address"
            )
            rows = {r["ip_address"]: r["password"] for r in cursor.fetchall()}
            assert rows["10.99.0.10"] == "enc_plain1"
            assert rows["10.99.0.11"] == "gAAAAAalready_enc"
            assert rows["10.99.0.12"] == "enc_plain2"

    def test_no_routers_does_not_error(self):
        from database.models import migrate_passwords

        migrate_passwords()

    def test_idempotent_second_call_no_double_encryption(self):
        from database.models import get_db, migrate_passwords

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO discovered_routers (ip_address, password, is_active) VALUES (?, ?, ?)",
                ("10.99.0.20", "first_plain", 1),
            )
            conn.commit()

        with patch("database.models.encrypt_password", side_effect=lambda p: f"gAAAAA{p}"):
            migrate_passwords()
            migrate_passwords()

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT password FROM discovered_routers WHERE ip_address = ?",
                ("10.99.0.20",),
            )
            row = cursor.fetchone()
            assert row["password"] == "gAAAAAfirst_plain"


class TestMigrateAddNameAlias:
    def test_emits_deprecation_warning(self):
        from database.models import migrate_add_name_alias

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            migrate_add_name_alias()
            deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecations) >= 1
            assert "deprecated" in str(deprecations[0].message).lower()

    def test_no_error_when_columns_already_exist(self):
        from database.models import migrate_add_name_alias

        migrate_add_name_alias()

    def test_idempotent(self):
        from database.models import migrate_add_name_alias

        migrate_add_name_alias()
        migrate_add_name_alias()

    def test_name_alias_column_exists_after_call(self):
        from database.models import get_db, migrate_add_name_alias

        migrate_add_name_alias()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(discovered_routers)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "name_alias" in columns

    def test_owner_id_column_exists_after_call(self):
        from database.models import get_db, migrate_add_name_alias

        migrate_add_name_alias()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(discovered_routers)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "owner_id" in columns

    def test_last_activity_column_exists_after_call(self):
        from database.models import get_db, migrate_add_name_alias

        migrate_add_name_alias()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(user_sessions)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "last_activity" in columns

    def test_session_timeout_column_exists_after_call(self):
        from database.models import get_db, migrate_add_name_alias

        migrate_add_name_alias()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(user_sessions)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "session_timeout" in columns

    def test_adds_columns_to_bare_table(self):
        import os
        import sqlite3
        import tempfile
        from unittest.mock import patch

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            conn = sqlite3.connect(tmp.name)
            conn.execute(
                "CREATE TABLE discovered_routers (id INTEGER PRIMARY KEY, ip_address TEXT)"
            )
            conn.execute("CREATE TABLE user_sessions (user_id INTEGER PRIMARY KEY)")
            conn.commit()
            conn.close()

            with (
                patch("database.models.DB_PATH", tmp.name),
                patch("database.models.os.path.dirname", return_value=os.path.dirname(tmp.name)),
            ):
                from database.models import migrate_add_name_alias

                migrate_add_name_alias()

            conn = sqlite3.connect(tmp.name)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(discovered_routers)")
            dr_cols = {row[1] for row in cursor.fetchall()}
            assert "name_alias" in dr_cols
            assert "owner_id" in dr_cols

            cursor.execute("PRAGMA table_info(user_sessions)")
            us_cols = {row[1] for row in cursor.fetchall()}
            assert "last_activity" in us_cols
            assert "session_timeout" in us_cols
            conn.close()
        finally:
            os.unlink(tmp.name)


class TestMigrateBackupScheduleColumns:
    def test_emits_deprecation_warning(self):
        from database.models import migrate_backup_schedule_columns

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            migrate_backup_schedule_columns()
            deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecations) >= 1
            assert "deprecated" in str(deprecations[0].message).lower()

    def test_no_error_when_columns_already_exist(self):
        from database.models import migrate_backup_schedule_columns

        migrate_backup_schedule_columns()

    def test_idempotent(self):
        from database.models import migrate_backup_schedule_columns

        migrate_backup_schedule_columns()
        migrate_backup_schedule_columns()

    def test_schedule_enabled_column_exists(self):
        from database.models import get_db, migrate_backup_schedule_columns

        migrate_backup_schedule_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(backup_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "schedule_enabled" in columns

    def test_schedule_hour_column_exists(self):
        from database.models import get_db, migrate_backup_schedule_columns

        migrate_backup_schedule_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(backup_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "schedule_hour" in columns

    def test_schedule_minute_column_exists(self):
        from database.models import get_db, migrate_backup_schedule_columns

        migrate_backup_schedule_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(backup_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "schedule_minute" in columns

    def test_adds_columns_to_bare_table(self):
        import os
        import sqlite3
        import tempfile
        from unittest.mock import patch

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            conn = sqlite3.connect(tmp.name)
            conn.execute("CREATE TABLE backup_settings (id INTEGER PRIMARY KEY)")
            conn.commit()
            conn.close()

            with (
                patch("database.models.DB_PATH", tmp.name),
                patch("database.models.os.path.dirname", return_value=os.path.dirname(tmp.name)),
            ):
                from database.models import migrate_backup_schedule_columns

                migrate_backup_schedule_columns()

            conn = sqlite3.connect(tmp.name)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(backup_settings)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "schedule_enabled" in columns
            assert "schedule_hour" in columns
            assert "schedule_minute" in columns
            conn.close()
        finally:
            os.unlink(tmp.name)


class TestMigratePdfSettingsColumns:
    def test_emits_deprecation_warning(self):
        from database.models import migrate_pdf_settings_columns

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            migrate_pdf_settings_columns()
            deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecations) >= 1
            assert "deprecated" in str(deprecations[0].message).lower()

    def test_no_error_when_columns_already_exist(self):
        from database.models import migrate_pdf_settings_columns

        migrate_pdf_settings_columns()

    def test_idempotent(self):
        from database.models import migrate_pdf_settings_columns

        migrate_pdf_settings_columns()
        migrate_pdf_settings_columns()

    def test_brand_name_column_exists(self):
        from database.models import get_db, migrate_pdf_settings_columns

        migrate_pdf_settings_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pdf_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "brand_name" in columns

    def test_hotspot_dns_column_exists(self):
        from database.models import get_db, migrate_pdf_settings_columns

        migrate_pdf_settings_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pdf_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "hotspot_dns" in columns

    def test_show_qr_column_exists(self):
        from database.models import get_db, migrate_pdf_settings_columns

        migrate_pdf_settings_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pdf_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "show_qr" in columns

    def test_cards_per_page_column_exists(self):
        from database.models import get_db, migrate_pdf_settings_columns

        migrate_pdf_settings_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pdf_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "cards_per_page" in columns

    def test_label_spacing_single_column_exists(self):
        from database.models import get_db, migrate_pdf_settings_columns

        migrate_pdf_settings_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pdf_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "label_spacing_single" in columns

    def test_label_spacing_dual_column_exists(self):
        from database.models import get_db, migrate_pdf_settings_columns

        migrate_pdf_settings_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pdf_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "label_spacing_dual" in columns

    def test_value_max_font_single_column_exists(self):
        from database.models import get_db, migrate_pdf_settings_columns

        migrate_pdf_settings_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pdf_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "value_max_font_single" in columns

    def test_value_max_font_dual_column_exists(self):
        from database.models import get_db, migrate_pdf_settings_columns

        migrate_pdf_settings_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pdf_settings)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "value_max_font_dual" in columns

    def test_adds_columns_to_bare_table(self):
        import os
        import sqlite3
        import tempfile
        from unittest.mock import patch

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            conn = sqlite3.connect(tmp.name)
            conn.execute("CREATE TABLE pdf_settings (id INTEGER PRIMARY KEY)")
            conn.commit()
            conn.close()

            with (
                patch("database.models.DB_PATH", tmp.name),
                patch("database.models.os.path.dirname", return_value=os.path.dirname(tmp.name)),
            ):
                from database.models import migrate_pdf_settings_columns

                migrate_pdf_settings_columns()

            conn = sqlite3.connect(tmp.name)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pdf_settings)")
            columns = {row[1] for row in cursor.fetchall()}
            expected = {
                "brand_name",
                "hotspot_dns",
                "show_qr",
                "cards_per_page",
                "label_spacing_single",
                "label_spacing_dual",
                "value_max_font_single",
                "value_max_font_dual",
            }
            assert expected.issubset(columns)
            conn.close()
        finally:
            os.unlink(tmp.name)


class TestMigrateCardBatchesColumns:
    def test_emits_deprecation_warning(self):
        from database.models import migrate_card_batches_columns

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            migrate_card_batches_columns()
            deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecations) >= 1
            assert "deprecated" in str(deprecations[0].message).lower()

    def test_no_error_when_columns_already_exist(self):
        from database.models import migrate_card_batches_columns

        migrate_card_batches_columns()

    def test_idempotent(self):
        from database.models import migrate_card_batches_columns

        migrate_card_batches_columns()
        migrate_card_batches_columns()

    def test_created_by_column_exists(self):
        from database.models import get_db, migrate_card_batches_columns

        migrate_card_batches_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(card_batches)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "created_by" in columns

    def test_customer_name_column_exists(self):
        from database.models import get_db, migrate_card_batches_columns

        migrate_card_batches_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(card_batches)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "customer_name" in columns

    def test_payment_status_column_exists(self):
        from database.models import get_db, migrate_card_batches_columns

        migrate_card_batches_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(card_batches)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "payment_status" in columns

    def test_sale_price_column_exists(self):
        from database.models import get_db, migrate_card_batches_columns

        migrate_card_batches_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(card_batches)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "sale_price" in columns

    def test_sold_at_column_exists(self):
        from database.models import get_db, migrate_card_batches_columns

        migrate_card_batches_columns()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(card_batches)")
            columns = {row["name"] for row in cursor.fetchall()}
            assert "sold_at" in columns

    def test_adds_columns_to_bare_table(self):
        import os
        import sqlite3
        import tempfile
        from unittest.mock import patch

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            conn = sqlite3.connect(tmp.name)
            conn.execute(
                "CREATE TABLE card_batches (id INTEGER PRIMARY KEY, router_key TEXT, count INTEGER)"
            )
            conn.commit()
            conn.close()

            with (
                patch("database.models.DB_PATH", tmp.name),
                patch("database.models.os.path.dirname", return_value=os.path.dirname(tmp.name)),
            ):
                from database.models import migrate_card_batches_columns

                migrate_card_batches_columns()

            conn = sqlite3.connect(tmp.name)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(card_batches)")
            columns = {row[1] for row in cursor.fetchall()}
            expected = {
                "created_by",
                "customer_name",
                "payment_status",
                "sale_price",
                "sold_at",
            }
            assert expected.issubset(columns)
            conn.close()
        finally:
            os.unlink(tmp.name)
