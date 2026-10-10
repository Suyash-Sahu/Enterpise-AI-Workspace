from sqlalchemy.orm import Session

from app.models.role import Role


def seed_roles(db: Session):
    roles = ["admin", "user"]

    for role_name in roles:
        exists = db.query(Role).filter(Role.name == role_name).first()

        if not exists:
            db.add(Role(name=role_name))

    db.commit()