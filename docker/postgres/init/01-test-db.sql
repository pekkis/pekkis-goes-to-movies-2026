-- Runs once, when the volume is first initialized.
-- Integration tests use their own database so they never touch development data.
CREATE DATABASE pgtm_test OWNER pgtm;
