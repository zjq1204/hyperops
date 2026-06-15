from django.db import migrations, models
import django.db.models.deletion


def migrate_singleton_ldap_to_default_instance(apps, schema_editor):
    LdapAuthConfig = apps.get_model("accounts", "LdapAuthConfig")
    LdapGroupMapping = apps.get_model("accounts", "LdapGroupMapping")
    Profile = apps.get_model("accounts", "Profile")

    config = LdapAuthConfig.objects.order_by("id").first()
    if config is None and (
        LdapGroupMapping.objects.exists()
        or Profile.objects.filter(auth_source="ldap").exists()
    ):
        config = LdapAuthConfig.objects.create(
            name="Default LDAP",
            slug="default",
            is_default=True,
        )

    if config is None:
        return

    config.name = config.name or "Default LDAP"
    config.slug = config.slug or "default"
    config.is_default = True
    config.save(update_fields=["name", "slug", "is_default"])

    LdapGroupMapping.objects.filter(ldap_config__isnull=True).update(
        ldap_config=config
    )
    Profile.objects.filter(
        auth_source="ldap",
        ldap_instance__isnull=True,
    ).update(ldap_instance=config)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_ldap_auth_config_and_profile_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="ldapauthconfig",
            name="name",
            field=models.CharField(default="Default LDAP", max_length=120),
        ),
        migrations.AddField(
            model_name="ldapauthconfig",
            name="slug",
            field=models.SlugField(default="default", max_length=64, unique=True),
        ),
        migrations.AddField(
            model_name="ldapauthconfig",
            name="is_default",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="profile",
            name="ldap_instance",
            field=models.ForeignKey(
                blank=True,
                help_text="LDAP instance that owns this directory identity.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="profiles",
                to="accounts.ldapauthconfig",
            ),
        ),
        migrations.AddField(
            model_name="ldapgroupmapping",
            name="ldap_config",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="group_mappings",
                to="accounts.ldapauthconfig",
            ),
        ),
        migrations.RunPython(
            migrate_singleton_ldap_to_default_instance,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="ldapgroupmapping",
            name="ldap_config",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="group_mappings",
                to="accounts.ldapauthconfig",
            ),
        ),
        migrations.RemoveField(
            model_name="ldapauthconfig",
            name="singleton_key",
        ),
        migrations.RemoveConstraint(
            model_name="ldapgroupmapping",
            name="accounts_ldap_group_mapping_unique_pair",
        ),
        migrations.AddConstraint(
            model_name="ldapgroupmapping",
            constraint=models.UniqueConstraint(
                fields=("ldap_config", "ldap_group_dn", "target_group"),
                name="accounts_ldap_group_mapping_unique_pair",
            ),
        ),
        migrations.AlterModelOptions(
            name="ldapauthconfig",
            options={
                "ordering": ["-is_default", "id"],
                "verbose_name": "LDAP configuration",
                "verbose_name_plural": "LDAP configurations",
            },
        ),
        migrations.AlterModelOptions(
            name="ldapgroupmapping",
            options={
                "ordering": [
                    "ldap_config__name",
                    "ldap_group_dn",
                    "target_group__name",
                    "id",
                ],
            },
        ),
    ]
