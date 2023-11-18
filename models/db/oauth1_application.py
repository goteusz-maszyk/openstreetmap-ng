from typing import Self

from sqlalchemy import ARRAY, Enum, ForeignKey, LargeBinary, Sequence, Unicode
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from lib.crypto import decrypt_b
from limits import OAUTH_APP_NAME_MAX_LENGTH
from models.db.base import Base
from models.db.created_at import CreatedAt
from models.db.updated_at import UpdatedAt
from models.db.user import User
from models.scope import Scope
from utils import updating_cached_property

# TODO: cascading delete
# TODO: move validation logic

class OAuth1Application(Base.Sequential, CreatedAt, UpdatedAt):
    __tablename__ = 'oauth1_application'

    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    user: Mapped[User] = relationship(back_populates='oauth1_applications', lazy='raise')
    name: Mapped[str] = mapped_column(Unicode, nullable=False)
    consumer_key: Mapped[str] = mapped_column(Unicode(40), nullable=False)
    consumer_secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scopes: Mapped[Sequence[Scope]] = mapped_column(ARRAY(Enum(Scope)), nullable=False)
    application_url: Mapped[str] = mapped_column(Unicode, nullable=False)
    callback_url: Mapped[str | None] = mapped_column(Unicode, nullable=True)

    # relationships (nested imports to avoid circular imports)
    from oauth1_token import OAuth1Token
    oauth1_tokens: Mapped[Sequence[OAuth1Token]] = relationship(back_populates='application', lazy='raise')

    @updating_cached_property(lambda self: self.consumer_secret_encrypted)
    def consumer_secret(self) -> str:
        return decrypt_b(self.consumer_secret_encrypted)

    # TODO: SQL
    @classmethod
    async def find_one_by_key(cls, key: str) -> Self | None:
        return await cls.find_one({'key_public': key})