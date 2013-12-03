
import ejson
import uuid


@ejson.register_serializer(uuid.UUID)
def serialize_uuid(instance):
    return instance.urn


@ejson.register_deserializer(uuid.UUID)
def deserialize_uuid(data):
    return uuid.UUID(data)
