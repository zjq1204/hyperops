from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_multi_ldap_instances"),
    ]

    operations = [
        migrations.AddField(
            model_name="ldapgroupmapping",
            name="mapping_scope",
            field=models.CharField(
                choices=[
                    ("group", "Specific LDAP group"),
                    ("all", "All LDAP users"),
                ],
                default="group",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="ldapgroupmapping",
            name="ldap_group_dn",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                max_length=512,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="ldapgroupmapping",
            name="accounts_ldap_group_mapping_unique_pair",
        ),
        migrations.AddConstraint(
            model_name="ldapgroupmapping",
            constraint=models.UniqueConstraint(
                fields=(
                    "ldap_config",
                    "mapping_scope",
                    "ldap_group_dn",
                    "target_group",
                ),
                name="accounts_ldap_group_mapping_unique_pair",
            ),
        ),
        migrations.AlterModelOptions(
            name="ldapgroupmapping",
            options={
                "ordering": [
                    "ldap_config__name",
                    "mapping_scope",
                    "ldap_group_dn",
                    "target_group__name",
                    "id",
                ],
            },
        ),
    ]
