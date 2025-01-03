from asyncio import TaskGroup
from collections.abc import Collection, Sequence
from typing import Literal

import cython
from shapely.geometry.base import BaseGeometry
from sqlalchemy import Select, func, select, union_all

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.options_context import apply_options_context
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment


class NoteCommentQuery:
    @staticmethod
    async def legacy_find_many_by_query(
        *,
        geometry: BaseGeometry | None = None,
        limit: int | None,
    ) -> Sequence[NoteComment]:
        """
        Find note comments by query.
        """
        async with db() as session:
            stmt = select(NoteComment)
            stmt = apply_options_context(stmt)
            where_and = [Note.visible_to(auth_user())]

            if geometry is not None:
                where_and.append(func.ST_Intersects(Note.point, func.ST_GeomFromText(geometry.wkt, 4326)))

            stmt = stmt.where(*where_and).order_by(NoteComment.created_at.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def resolve_comments(
        notes: Collection[Note],
        *,
        per_note_sort: Literal['asc', 'desc'] = 'desc',
        per_note_limit: int | None,
        resolve_rich_text: bool = True,
    ) -> Sequence[NoteComment]:
        """
        Resolve comments for notes.
        """
        if not notes:
            return ()
        id_comments_map: dict[int, list[NoteComment]] = {}
        for note in notes:
            id_comments_map[note.id] = note.comments = []

        async with db() as session:
            stmts: list[Select] = [None] * len(notes)  # pyright: ignore[reportAssignmentType]
            i: cython.int
            for i, note in enumerate(notes):
                stmt_ = select(NoteComment.id).where(
                    NoteComment.note_id == note.id,
                    NoteComment.created_at <= note.updated_at,
                )
                if per_note_limit is not None:
                    subq = (
                        stmt_.order_by(
                            NoteComment.created_at.asc() if per_note_sort == 'asc' else NoteComment.created_at.desc()
                        )
                        .limit(per_note_limit)
                        .subquery()
                    )
                    stmt_ = select(subq.c.id).select_from(subq)
                stmts[i] = stmt_

            stmt = (
                select(NoteComment)
                .where(NoteComment.id.in_(union_all(*stmts).subquery().select()))
                .order_by(NoteComment.created_at.asc())
            )
            stmt = apply_options_context(stmt)
            comments: Sequence[NoteComment] = (await session.scalars(stmt)).all()

        current_note_id: int = 0
        current_comments: list[NoteComment] = []
        for comment in comments:
            note_id = comment.note_id
            if current_note_id != note_id:
                current_note_id = note_id
                current_comments = id_comments_map[note_id]
            current_comments.append(comment)

        if resolve_rich_text:
            async with TaskGroup() as tg:
                for comment in comments:
                    tg.create_task(comment.resolve_rich_text())

        return comments
