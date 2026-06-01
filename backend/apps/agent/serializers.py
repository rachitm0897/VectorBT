from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=1000)

    def validate_message(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("message is required.")
        return value
