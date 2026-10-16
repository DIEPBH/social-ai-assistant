from django.db import migrations

def update_commune_coordinates(apps, schema_editor):
    AdministrativeArea = apps.get_model("social_messages", "AdministrativeArea")
    # Cập nhật chuẩn xác tọa độ Xã Phú Xuyên (phía Tây Đại Từ, giáp Tuyên Quang)
    AdministrativeArea.objects.filter(code="TN_52").update(
        latitude=21.6641,
        longitude=105.5541
    )
    AdministrativeArea.objects.filter(name="Xã Phú Xuyên").update(
        latitude=21.6641,
        longitude=105.5541
    )
    # Cập nhật chuẩn xác tọa độ Xã Phú Lạc
    AdministrativeArea.objects.filter(code="TN_48").update(
        latitude=21.6873,
        longitude=105.6072
    )
    AdministrativeArea.objects.filter(name="Xã Phú Lạc").update(
        latitude=21.6873,
        longitude=105.6072
    )

class Migration(migrations.Migration):
    dependencies = [
        ("social_messages", "0028_rename_district_to_cluster_and_reimport_92_communes"),
    ]

    operations = [
        migrations.RunPython(update_commune_coordinates, reverse_code=migrations.RunPython.noop),
    ]
