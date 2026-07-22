import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app as contracts_app


class NewContractNotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temp_dir.name) / "contracts.json"
        self.original_data_file = contracts_app.DATA_FILE
        self.original_smtp_host = contracts_app.SMTP_HOST
        self.original_smtp_port = contracts_app.SMTP_PORT
        self.original_smtp_use_tls = contracts_app.SMTP_USE_TLS
        self.original_smtp_username = contracts_app.SMTP_USERNAME
        self.original_smtp_password = contracts_app.SMTP_PASSWORD
        self.original_smtp_from = contracts_app.SMTP_FROM
        contracts_app.DATA_FILE = str(self.data_file)
        contracts_app.SMTP_HOST = "smtp.example.test"
        contracts_app.SMTP_PORT = 587
        contracts_app.SMTP_USE_TLS = True
        contracts_app.SMTP_USERNAME = "mailer"
        contracts_app.SMTP_PASSWORD = "secret"
        contracts_app.SMTP_FROM = "no-reply@example.test"
        contracts_app.app.config["TESTING"] = True
        self.client = contracts_app.app.test_client()

    def tearDown(self):
        contracts_app.DATA_FILE = self.original_data_file
        contracts_app.SMTP_HOST = self.original_smtp_host
        contracts_app.SMTP_PORT = self.original_smtp_port
        contracts_app.SMTP_USE_TLS = self.original_smtp_use_tls
        contracts_app.SMTP_USERNAME = self.original_smtp_username
        contracts_app.SMTP_PASSWORD = self.original_smtp_password
        contracts_app.SMTP_FROM = self.original_smtp_from
        self.temp_dir.cleanup()

    def test_public_submission_saves_contract_and_notifies_aurelie(self):
        with self.client.session_transaction() as session:
            session["form_token"] = "valid-token"

        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        with patch.object(contracts_app.smtplib, "SMTP", return_value=smtp) as smtp_class:
            response = self.client.post(
                "/submit",
                data={
                    "form_token": "valid-token",
                    "prenom": "Jeanne",
                    "nom": "Dupont",
                    "entreprise": "Exemple SAS",
                    "bts": "BTS NDRC",
                    "date_debut": "2026-09-01",
                },
            )

        self.assertEqual(response.status_code, 200)
        saved_contracts = json.loads(self.data_file.read_text())
        self.assertEqual(len(saved_contracts), 1)
        self.assertEqual(saved_contracts[0]["status"], "A traiter")
        smtp_class.assert_called_once_with("smtp.example.test", 587, timeout=10)
        smtp.starttls.assert_called_once_with()
        smtp.login.assert_called_once_with("mailer", "secret")
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["To"], "aurelie@integraleacademy.com")
        self.assertEqual(message["Subject"], "Nouveau contrat d'apprentissage à traiter")
        self.assertIn("Jeanne Dupont", message.get_content())


if __name__ == "__main__":
    unittest.main()
