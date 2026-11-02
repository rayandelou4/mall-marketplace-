from django.db import migrations, models


def merge_conversations(apps, schema_editor):
    Conversation = apps.get_model("messaging", "Conversation")
    ConversationParticipant = apps.get_model("messaging", "ConversationParticipant")
    Message = apps.get_model("messaging", "Message")
    Product = apps.get_model("catalog", "Product")
    database = schema_editor.connection.alias

    grouped = {}
    conversations = Conversation.objects.using(database).order_by("created_at", "pk")
    for conversation in conversations.iterator():
        participant_ids = tuple(
            ConversationParticipant.objects.using(database)
            .filter(conversation_id=conversation.pk)
            .order_by("user_id")
            .values_list("user_id", flat=True)
        )
        if len(participant_ids) != 2:
            continue
        grouped.setdefault(participant_ids, []).append(conversation.pk)

    for conversation_ids in grouped.values():
        if len(conversation_ids) < 2:
            continue
        primary_id, *duplicate_ids = conversation_ids
        primary = Conversation.objects.using(database).get(pk=primary_id)
        for duplicate in Conversation.objects.using(database).filter(pk__in=duplicate_ids).iterator():
            if duplicate.product_id:
                product = Product.objects.using(database).get(pk=duplicate.product_id)
                primary.products.add(product)
            Message.objects.using(database).filter(conversation_id=duplicate.pk).update(
                conversation_id=primary.pk
            )
            duplicate.delete(using=database)
        latest_activity = (
            Conversation.objects.using(database)
            .filter(pk__in=conversation_ids)
            .order_by("-updated_at")
            .values_list("updated_at", flat=True)
            .first()
        )
        Conversation.objects.using(database).filter(pk=primary_id).update(updated_at=latest_activity)

    for conversation in Conversation.objects.using(database).iterator():
        if conversation.product_id:
            product = Product.objects.using(database).get(pk=conversation.product_id)
            conversation.products.add(product)


class Migration(migrations.Migration):
    dependencies = [
        ("messaging", "0003_message_edit_reply"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="products",
            field=models.ManyToManyField(blank=True, related_name="conversations", to="catalog.product"),
        ),
        migrations.RunPython(merge_conversations),
        migrations.RemoveField(
            model_name="conversation",
            name="product",
        ),
    ]