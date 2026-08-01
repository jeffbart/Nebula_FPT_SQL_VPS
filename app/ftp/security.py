"""
Security Module - Gerenciamento de senhas com bcrypt + PBKDF2
"""

import os
import bcrypt
import hmac
from hashlib import pbkdf2_hmac
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class PasswordManager:
    """Gerenciador de senhas com suporte a bcrypt e PBKDF2 (fallback)"""
    
    # Bcrypt: 12 rounds (recomendado pelo OWASP)
    BCRYPT_ROUNDS = 12
    
    # PBKDF2: 600k iterations (OWASP recomendação 2023)
    PBKDF2_ITERATIONS = 600000
    PBKDF2_HASH_NAME = 'sha256'
    PBKDF2_SALT_SIZE = 32  # 256 bits
    
    @staticmethod
    def hash_password_bcrypt(password: str) -> str:
        """
        Gera hash bcrypt de uma senha
        
        Args:
            password: Senha em plaintext (string)
            
        Returns:
            Hash bcrypt em formato $2b$... (str)
            
        Raises:
            ValueError: Se senha vazia ou inválida
        """
        if not password or not isinstance(password, str):
            raise ValueError("Senha deve ser string não-vazia")
        
        try:
            salt = bcrypt.gensalt(rounds=PasswordManager.BCRYPT_ROUNDS)
            hash_bytes = bcrypt.hashpw(password.encode('utf-8'), salt)
            return hash_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Erro ao gerar hash bcrypt: {e}")
            raise
    
    @staticmethod
    def verify_password_bcrypt(password: str, hash_str: str) -> bool:
        """
        Valida senha contra hash bcrypt
        
        Args:
            password: Senha em plaintext
            hash_str: Hash bcrypt armazenado
            
        Returns:
            True se válido, False caso contrário
        """
        if not password or not hash_str:
            return False
        
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hash_str.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Erro ao verificar hash bcrypt: {e}")
            return False
    
    @staticmethod
    def hash_password_pbkdf2(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
        """
        Gera hash PBKDF2 de uma senha (fallback para compatibilidade)
        
        Args:
            password: Senha em plaintext
            salt: Salt customizado (gera novo se None)
            
        Returns:
            Tupla (hash_hex, salt_hex) ambos em string hexadecimal
        """
        if not password or not isinstance(password, str):
            raise ValueError("Senha deve ser string não-vazia")
        
        if not salt:
            salt = os.urandom(PasswordManager.PBKDF2_SALT_SIZE)
        
        try:
            hash_obj = pbkdf2_hmac(
                PasswordManager.PBKDF2_HASH_NAME,
                password.encode('utf-8'),
                salt,
                PasswordManager.PBKDF2_ITERATIONS
            )
            return hash_obj.hex(), salt.hex()
        except Exception as e:
            logger.error(f"Erro ao gerar hash PBKDF2: {e}")
            raise
    
    @staticmethod
    def verify_password_pbkdf2(password: str, stored_hash: str, stored_salt: str) -> bool:
        """
        Valida senha contra hash PBKDF2
        
        Args:
            password: Senha em plaintext
            stored_hash: Hash armazenado em formato hex
            stored_salt: Salt armazenado em formato hex
            
        Returns:
            True se válido, False caso contrário
        """
        if not password or not stored_hash or not stored_salt:
            return False
        
        try:
            salt_bytes = bytes.fromhex(stored_salt)
            hash_obj = pbkdf2_hmac(
                PasswordManager.PBKDF2_HASH_NAME,
                password.encode('utf-8'),
                salt_bytes,
                PasswordManager.PBKDF2_ITERATIONS
            )
            return hmac.compare_digest(hash_obj.hex(), stored_hash)
        except Exception as e:
            logger.error(f"Erro ao verificar hash PBKDF2: {e}")
            return False
    
    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """
        Valida força da senha
        
        Critérios:
        - Mínimo 8 caracteres
        - Contém maiúsculas
        - Contém minúsculas
        - Contém números
        - Contém caracteres especiais (opcional)
        
        Args:
            password: Senha para validar
            
        Returns:
            Tupla (válida, mensagem)
        """
        if len(password) < 8:
            return False, "Senha deve ter no mínimo 8 caracteres"
        
        if not any(c.isupper() for c in password):
            return False, "Senha deve conter pelo menos uma letra maiúscula"
        
        if not any(c.islower() for c in password):
            return False, "Senha deve conter pelo menos uma letra minúscula"
        
        if not any(c.isdigit() for c in password):
            return False, "Senha deve conter pelo menos um número"
        
        # Caracteres especiais são opcionais mas recomendados
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if any(c in special_chars for c in password):
            return True, "Senha forte com caracteres especiais"
        
        return True, "Senha válida"
    
    @staticmethod
    def needs_rehash(password_hash: str, hash_type: str = "bcrypt") -> bool:
        """
        Verifica se senha precisa ser re-hasheada (migração de algoritmo)
        
        Args:
            password_hash: Hash da senha
            hash_type: Tipo de hash ("bcrypt" ou "pbkdf2")
            
        Returns:
            True se precisa re-hasheada (algoritmo antigo/fraco)
        """
        # Se é PBKDF2, precisa migrar para bcrypt
        if hash_type == "pbkdf2":
            return True
        
        # Se é bcrypt mas com rounds < 12, precisa re-hasheada
        if hash_type == "bcrypt" and password_hash.startswith("$2b$"):
            try:
                rounds = int(password_hash.split("$")[2])
                if rounds < PasswordManager.BCRYPT_ROUNDS:
                    return True
            except:
                pass
        
        return False


__all__ = ["PasswordManager"]
