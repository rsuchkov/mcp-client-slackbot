import pytest

from mcp_simple_slackbot.database.encryption import EncryptionService


class TestEncryptionService:
    def test_generate_key(self):
        """Test key generation produces valid Fernet keys."""
        key = EncryptionService.generate_key()
        assert isinstance(key, str)
        assert len(key) == 44  # Base64 encoded 32-byte key

    def test_encrypt_decrypt_roundtrip(self, encryption_service: EncryptionService):
        """Test encryption and decryption round trip."""
        plaintext = "secret_password_123"
        
        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)
        
        assert decrypted == plaintext
        assert encrypted != plaintext

    def test_encrypt_empty_string(self, encryption_service: EncryptionService):
        """Test encryption of empty string."""
        encrypted = encryption_service.encrypt("")
        decrypted = encryption_service.decrypt(encrypted)
        
        assert decrypted == ""
        assert encrypted == ""

    def test_different_plaintexts_produce_different_ciphertexts(
        self, encryption_service: EncryptionService
    ):
        """Test that different plaintexts produce different ciphertexts."""
        plaintext1 = "password1"
        plaintext2 = "password2"
        
        encrypted1 = encryption_service.encrypt(plaintext1)
        encrypted2 = encryption_service.encrypt(plaintext2)
        
        assert encrypted1 != encrypted2

    def test_same_plaintext_produces_different_ciphertexts(
        self, encryption_service: EncryptionService
    ):
        """Test that encrypting the same plaintext twice produces different results."""
        plaintext = "same_password"
        
        encrypted1 = encryption_service.encrypt(plaintext)
        encrypted2 = encryption_service.encrypt(plaintext)
        
        # Fernet includes random IV, so same plaintext should produce different
        # ciphertext
        assert encrypted1 != encrypted2
        
        # But both should decrypt to the same plaintext
        assert encryption_service.decrypt(encrypted1) == plaintext
        assert encryption_service.decrypt(encrypted2) == plaintext

    def test_init_with_custom_key(self):
        """Test initialization with custom key."""
        custom_key = EncryptionService.generate_key()
        service = EncryptionService(custom_key)
        
        plaintext = "test_message"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == plaintext

    def test_init_from_env_encryption_key(self, monkeypatch):
        """Test initialization from ENCRYPTION_KEY environment variable."""
        test_key = EncryptionService.generate_key()
        monkeypatch.setenv("ENCRYPTION_KEY", test_key)
        
        service = EncryptionService()
        
        plaintext = "test_from_env"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == plaintext

    def test_init_from_env_master_password(self, monkeypatch):
        """Test initialization from MASTER_PASSWORD environment variable."""
        monkeypatch.setenv("MASTER_PASSWORD", "test_master_password")
        monkeypatch.setenv("ENCRYPTION_SALT", "test_salt")
        
        service = EncryptionService()
        
        plaintext = "test_from_master_password"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == plaintext

    def test_init_without_env_variables_raises_error(self, monkeypatch):
        """Test that initialization without required env variables raises error."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.delenv("MASTER_PASSWORD", raising=False)
        
        with pytest.raises(
            ValueError, match="Either ENCRYPTION_KEY or MASTER_PASSWORD"
        ):
            EncryptionService()

    def test_master_password_deterministic(self, monkeypatch):
        """Test that same master password produces same encryption key."""
        monkeypatch.setenv("MASTER_PASSWORD", "consistent_password")
        monkeypatch.setenv("ENCRYPTION_SALT", "consistent_salt")
        
        service1 = EncryptionService()
        service2 = EncryptionService()
        
        plaintext = "test_consistency"
        encrypted1 = service1.encrypt(plaintext)
        decrypted2 = service2.decrypt(encrypted1)
        
        assert decrypted2 == plaintext

    def test_unicode_text_encryption(self, encryption_service: EncryptionService):
        """Test encryption of unicode text."""
        unicode_text = "пароль_тест_🔐"
        
        encrypted = encryption_service.encrypt(unicode_text)
        decrypted = encryption_service.decrypt(encrypted)
        
        assert decrypted == unicode_text

    def test_long_text_encryption(self, encryption_service: EncryptionService):
        """Test encryption of long text."""
        long_text = "a" * 10000
        
        encrypted = encryption_service.encrypt(long_text)
        decrypted = encryption_service.decrypt(encrypted)
        
        assert decrypted == long_text