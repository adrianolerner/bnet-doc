from datetime import date, datetime
from enum import Enum as PyEnum
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

class AttributeType(str, PyEnum):
    STRING = "String"
    INTEGER = "Integer"
    DATE = "Date"
    BOOLEAN = "Boolean"
    PASSWORD = "Password"
    FILE = "File"
    RICH_TEXT = "RichText"

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )
    display_order = Column(Integer, default=0, nullable=False)

    # Relacionamentos
    attributes = relationship(
        "Attribute", back_populates="category", cascade="all, delete-orphan", order_by="Attribute.display_order"
    )
    entities = relationship(
        "Entity", back_populates="category", cascade="all, delete-orphan"
    )


class Attribute(Base):
    __tablename__ = "attributes"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    type = Column(Enum(AttributeType), nullable=False)
    is_required = Column(Boolean, default=False, nullable=False)
    display_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # Relacionamentos
    category = relationship("Category", back_populates="attributes")
    values = relationship(
        "Value", back_populates="attribute", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_category_attribute_name"),
    )


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # Relacionamentos
    category = relationship("Category", back_populates="entities")
    values = relationship(
        "Value", back_populates="entity", cascade="all, delete-orphan"
    )


class Value(Base):
    __tablename__ = "values"

    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    attribute_id = Column(
        Integer, ForeignKey("attributes.id", ondelete="CASCADE"), nullable=False
    )

    # Valores específicos por tipo de dados (EAV)
    value_string = Column(Text, nullable=True)
    value_integer = Column(Integer, nullable=True)
    value_date = Column(Date, nullable=True)
    value_boolean = Column(Boolean, nullable=True)

    # Relacionamentos
    entity = relationship("Entity", back_populates="values")
    attribute = relationship("Attribute", back_populates="values")

    __table_args__ = (
        UniqueConstraint("entity_id", "attribute_id", name="uq_entity_attribute_value"),
    )

class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String(255), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class ModificationLog(Base):
    __tablename__ = "modification_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity_id = Column(Integer, index=True, nullable=True) # ID of the modified item
    category_name = Column(String(255), nullable=True)
    action = Column(String(50), nullable=False) # CREATE, UPDATE, DELETE
    username = Column(String(255), nullable=True) # User who made the change
    created_at = Column(DateTime, default=datetime.now, nullable=False)

