"""
Seed script — creates the admin user if it doesn't exist.
Run once after migrations: python -m scripts.seed_admin
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.user import User
from app.core.auth import hash_password

settings = get_settings()


async def seed():
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        result = await session.execute(select(User).where(User.email == settings.admin_email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"✓ Admin user already exists: {settings.admin_email}")
        else:
            user = User(
                email=settings.admin_email,
                hashed_password=hash_password(settings.admin_password),
            )
            session.add(user)
            await session.commit()
            print(f"✓ Created admin user: {settings.admin_email}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
