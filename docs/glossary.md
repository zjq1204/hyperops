# HyperOps Glossary

This glossary defines the terms used by the phase-one object-storage design.

| Term | Definition |
| --- | --- |
| 平台级配置 / platform configuration | A singleton configuration belonging to the HyperOps installation, not to an enterprise or tenant. |
| 飞书应用 / Feishu app | The single Feishu OAuth application used to authenticate users into HyperOps. |
| 本地组 / local group | An existing HyperOps group bound to the Feishu app; its roles determine workbench and console access. |
| HyperOps 用户 | The existing local user record used for login, authorization, ownership, and audit references. |
| 飞书身份 / Feishu identity | The external Feishu `open_id` record linked to a local HyperOps user. It is not the local user itself. |
| 资源池 / resource pool | The administrator-managed Alibaba Cloud account and region used by the platform. Phase one has one enabled pool. |
| RAM 用户 / RAM user | The Alibaba Cloud programmatic identity created for one HyperOps user. It cannot log in to the cloud console. |
| Bucket | An OSS storage container owned by one HyperOps user. Its final cloud name and region are immutable after creation. |
| 业务名称 / business name | The user-entered label used with the administrator template to render a final Bucket name. |
| 访问密钥 / access key | An AK/SK pair belonging to a user's RAM user. All keys for that RAM user share access to the user's Buckets. |
| 有效密钥 / effective key | A key that has not been revoked or deleted and may be active or temporarily disabled according to its state. |
| 申请批次 / application batch | One user submission containing one or more Bucket application items. |
| 申请项 / application item | One independent Bucket request within a batch, with its own state, result, retry, and audit trail. |
| 待删除 / pending deletion | A released Bucket retained for seven days, inaccessible through the user's policy and not counted against quota. |
| 删除受阻 / deletion blocked | A Bucket that cannot be deleted because it still contains data or unfinished cloud operations. |
| 公共读 / public read | An administrator-approved ACL mode in which objects may be read anonymously. It requires a reason and audit record. |
| 平台管理员 / platform administrator | The existing HyperOps administrator permission used for object-storage management. No new role is added. |
| 需人工处理 / manual action required | A terminal or paused state requiring an administrator because automatic recovery cannot establish a safe result. |
| 一次性交付 / one-time delivery | The first full display of a newly issued AK/SK; the delivery ticket is consumed after one successful retrieval. |
