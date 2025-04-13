from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Generate hash for "secret123"
password = "secret123"
hashed_password = pwd_context.hash(password)
print(f"Password: {password}")
print(f"Hashed password: {hashed_password}")

# Verify the hash
print(f"Verification: {pwd_context.verify(password, hashed_password)}") 