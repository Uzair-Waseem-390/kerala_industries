import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    # Genuinely two separate operations, not a rename: JumboBinding is
    # dropped (client decided this Jumbo attribute isn't needed), CoreName
    # is a new, unrelated attribute added to the Cores family. Written by
    # hand because Django's makemigrations interactively asks "was this
    # renamed?" and can't run non-interactively.

    dependencies = [
        ("purchases", "0022_family"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CoreName",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("value", models.CharField(max_length=255, unique=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("deleted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_deleted", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Core Name",
                "verbose_name_plural": "Core Names",
                "ordering": ["value"],
            },
        ),
        migrations.DeleteModel(
            name="JumboBinding",
        ),
    ]
