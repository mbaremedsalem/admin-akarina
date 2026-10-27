import uuid

from django.db import migrations, models


def generer_references(apps, schema_editor):
    EchangeCadeau = apps.get_model("fidelite", "EchangeCadeau")
    for echange in EchangeCadeau.objects.filter(reference__isnull=True):
        echange.reference = f"CAD-{uuid.uuid4().hex[:10].upper()}"
        echange.save(update_fields=["reference"])


def effacer_references(apps, schema_editor):
    EchangeCadeau = apps.get_model("fidelite", "EchangeCadeau")
    EchangeCadeau.objects.update(reference=None)


class Migration(migrations.Migration):

    dependencies = [
        ("fidelite", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="echangecadeau",
            name="reference",
            field=models.CharField(editable=False, max_length=25, null=True, unique=True),
        ),
        migrations.RunPython(generer_references, effacer_references),
        migrations.AlterField(
            model_name="echangecadeau",
            name="reference",
            field=models.CharField(editable=False, max_length=25, unique=True),
        ),
    ]
