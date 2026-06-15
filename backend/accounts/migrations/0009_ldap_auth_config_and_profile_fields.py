from django.db import migrations, models


def mark_oauth_profiles(apps, schema_editor):
    Profile = apps.get_model("accounts", "Profile")
    SocialAccount = apps.get_model("socialaccount", "SocialAccount")

    oauth_user_ids = list(
        SocialAccount.objects.values_list("user_id", flat=True).distinct()
    )
    if oauth_user_ids:
        Profile.objects.filter(user_id__in=oauth_user_ids).update(auth_source="oauth")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_profile_jenkins_notifications_groupnotificationconfig"),
        ("socialaccount", "0006_alter_socialaccount_extra_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="auth_source",
            field=models.CharField(
                choices=[
                    ("local", "Local"),
                    ("ldap", "LDAP"),
                    ("oauth", "OAuth"),
                ],
                default="local",
                help_text="Primary authentication source for the user.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="ldap_dn",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Resolved LDAP distinguished name for the user.",
                max_length=512,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="ldap_group_dns_snapshot",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Last LDAP group DNS returned during successful sync.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="ldap_last_synced_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Last successful LDAP profile/group sync time.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="ldap_uid",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Directory uid used for LDAP login.",
                max_length=255,
            ),
        ),
        migrations.CreateModel(
            name="LdapAuthConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "singleton_key",
                    models.CharField(
                        default="default",
                        editable=False,
                        max_length=32,
                        unique=True,
                    ),
                ),
                ("enabled", models.BooleanField(default=False)),
                ("host", models.CharField(blank=True, default="", max_length=255)),
                ("port", models.PositiveIntegerField(default=389)),
                ("use_ssl", models.BooleanField(default=False)),
                ("start_tls", models.BooleanField(default=False)),
                ("bind_dn", models.CharField(blank=True, default="", max_length=512)),
                ("bind_password_encrypted", models.TextField(blank=True, default="")),
                (
                    "user_base_dn",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                (
                    "user_filter_template",
                    models.CharField(
                        blank=True,
                        default="(&(objectClass=person)(uid={username}))",
                        max_length=512,
                    ),
                ),
                (
                    "group_base_dn",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                (
                    "group_filter_template",
                    models.CharField(
                        blank=True,
                        default="(&(objectClass=groupOfNames)(member={user_dn}))",
                        max_length=512,
                    ),
                ),
                ("uid_attr", models.CharField(blank=True, default="uid", max_length=128)),
                (
                    "email_attr",
                    models.CharField(blank=True, default="mail", max_length=128),
                ),
                (
                    "first_name_attr",
                    models.CharField(blank=True, default="givenName", max_length=128),
                ),
                (
                    "last_name_attr",
                    models.CharField(blank=True, default="sn", max_length=128),
                ),
                (
                    "display_name_attr",
                    models.CharField(blank=True, default="displayName", max_length=128),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "LDAP configuration",
                "verbose_name_plural": "LDAP configuration",
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="LdapGroupMapping",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ldap_group_dn", models.CharField(db_index=True, max_length=512)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "target_group",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="ldap_group_mappings",
                        to="auth.group",
                    ),
                ),
            ],
            options={
                "ordering": ["ldap_group_dn", "target_group__name", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="ldapgroupmapping",
            constraint=models.UniqueConstraint(
                fields=("ldap_group_dn", "target_group"),
                name="accounts_ldap_group_mapping_unique_pair",
            ),
        ),
        migrations.RunPython(mark_oauth_profiles, migrations.RunPython.noop),
    ]
