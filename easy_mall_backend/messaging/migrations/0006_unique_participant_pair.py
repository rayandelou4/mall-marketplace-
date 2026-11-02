from django.db import migrations, models


def populate_participant_pair_keys(apps, schema_editor):
    Conversation = apps.get_model("messaging", "Conversation")
    ConversationParticipant = apps.get_model("messaging", "ConversationParticipant")
    Message = apps.get_model("messaging", "Message")
    database = schema_editor.connection.alias
    grouped = {}

    for conversation in Conversation.objects.using(database).order_by("created_at", "pk").iterator():
        participant_ids = tuple(
            ConversationParticipant.objects.using(database)
            .filter(conversation_id=conversation.pk)
            .order_by("user_id")
            .values_list("user_id", flat=True)
        )
        if len(participant_ids) == 2:
            pair = tuple(sorted(str(user_id) for user_id in participant_ids))
            grouped.setdefault(pair, []).append((conversation, participant_ids))

    for pair, conversations in grouped.items():
        primary, participant_ids = conversations[0]
        participant_visibility = {user_id: [] for user_id in participant_ids}

        for conversation, _ in conversations:
            for participant in ConversationParticipant.objects.using(database).filter(
                conversation_id=conversation.pk
            ):
                participant_visibility[participant.user_id].append(participant.is_hidden)

            if conversation.pk == primary.pk:
                continue

            product_ids = list(conversation.products.values_list("pk", flat=True))
            if product_ids:
                primary.products.add(*product_ids)
            Message.objects.using(database).filter(conversation_id=conversation.pk).update(
                conversation_id=primary.pk
            )
            conversation.delete(using=database)

        for user_id, visibility in participant_visibility.items():
            ConversationParticipant.objects.using(database).filter(
                conversation_id=primary.pk, user_id=user_id
            ).update(is_hidden=all(visibility))

        latest_activity = max(conversation.updated_at for conversation, _ in conversations)
        Conversation.objects.using(database).filter(pk=primary.pk).update(
            participant_pair_key=":".join(pair),
            updated_at=latest_activity,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0005_hide_conversation_per_participant"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="participant_pair_key",
            field=models.CharField(editable=False, max_length=73, null=True),
        ),
        migrations.RunPython(populate_participant_pair_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="conversation",
            name="participant_pair_key",
            field=models.CharField(editable=False, max_length=73, null=True, unique=True),
        ),
    ]