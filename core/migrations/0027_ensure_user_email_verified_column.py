from django.db import migrations


def ensure_email_verified_column(apps, schema_editor):
    table_name = "core_user"
    column_name = "email_verified"

    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            col.name for col in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }
        if column_name in existing_columns:
            return

        vendor = schema_editor.connection.vendor
        if vendor == "sqlite":
            schema_editor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} bool NOT NULL DEFAULT 0"
            )
        elif vendor == "postgresql":
            schema_editor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} boolean NOT NULL DEFAULT false"
            )
        elif vendor == "mysql":
            schema_editor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} bool NOT NULL DEFAULT 0"
            )
        else:
            schema_editor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} boolean NOT NULL DEFAULT false"
            )


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("core", "0026_emailverificationtoken"),
    ]

    operations = [
        migrations.RunPython(ensure_email_verified_column, migrations.RunPython.noop),
    ]
