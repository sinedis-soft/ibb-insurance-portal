# Access Control Matrix

This matrix is the MVP contract for portal access checks. Bitrix24 remains the
business system of record; the portal only stores minimal links and local
authorization state.

| Role | Object type | Action | Expected result | HTTP status | Audit required |
| --- | --- | --- | --- | --- | --- |
| unauthenticated | company | list | denied | 401 | no |
| client_executor | company | read/list | active linked companies only | 200 | no |
| client_executor | company | create | allowed through create_application scope | 200 | no |
| client_executor | company | approve | denied | 403 | yes |
| client_executor | application | read | allowed for active linked company | 200 | no |
| client_executor | application | create/edit/submit | allowed for active linked company | 200 | no |
| client_executor | application | approve/return_for_revision | denied | 403 | yes |
| client_executor | policy | read | allowed for accessible application | 200 | no |
| client_executor | policy | request_policy_email/request_policy_telegram | allowed for accessible application | 200 | no |
| client_executor | document | upload/read_document_metadata/download | allowed for accessible application | 200 | no |
| client_executor | search result | search | own accessible applications and documents only | 200 | no |
| client_admin | company | read/list | active linked companies only | 200 | no |
| client_admin | company | create | allowed through create_application scope | 200 | no |
| client_admin | application | read/create/edit/submit | allowed for active linked company | 200 | no |
| client_admin | application | approve/return_for_revision | allowed for active linked company | 200 | no |
| client_admin | policy | read/request_policy_email/request_policy_telegram | allowed for accessible application | 200 | no |
| client_admin | document | upload/read_document_metadata/download | allowed for accessible application | 200 | no |
| client_admin | company | assign_role/revoke_role | denied through superadmin API | 403 | yes |
| client_admin | search result | search | own accessible applications and documents only | 200 | no |
| client_viewer | company | read/list | active linked companies only | 200 | no |
| client_viewer | company | create | denied | 403 | yes |
| client_viewer | application | read | allowed for active linked company | 200 | no |
| client_viewer | application | create/edit/submit/approve/return_for_revision | denied | 403 | yes |
| client_viewer | policy | read | allowed for accessible application | 200 | no |
| client_viewer | policy | request_policy_email/request_policy_telegram | denied | 403 | yes |
| client_viewer | document | read_document_metadata | allowed for accessible application | 200 | no |
| client_viewer | document | upload/download | denied | 403 | yes |
| client_viewer | search result | search | own accessible read scope only | 200 | no |
| partner | company | list via /me/companies | no client company-role rows | 200 | no |
| partner | partner client | list | active linked clients in partner scope only | 200 | no |
| partner | application | read | assigned partner applications only | 200 | no |
| partner | application | submit/upload_document | allowed only for active own partner application | 200 | no |
| partner | application | read another partner application | denied and masked | 404 | yes |
| partner | policy | read | own partner application status/number only | 200 | no |
| partner | policy | request_policy_email/request_policy_telegram/download | denied | 403 | yes |
| partner | document | read_document_metadata/upload | allowed only for own non-policy partner documents | 200 | no |
| partner | document | download/policy file/client documents | denied | 403 | yes |
| partner | search result | search | partner-assigned application/document scope only | 200 | no |
| superadmin | company | assign_role/revoke_role | allowed | 200/201 | yes |
| superadmin | partner client | create/revoke | allowed | 200/201 | yes |
| superadmin | application/policy/document | read | allowed for inspection | 200 | no |
| superadmin | search result | search | all portal-linked objects | 200 | no |
| revoked/pending/rejected client role | company/application/policy/document/search | any | denied or empty scope | 403/404/200 empty | yes on deny |
| blocked user | company/application/policy/document/search | any | denied or empty scope | 403/404/200 empty | yes on deny |
| any non-owner | application/document/policy | guessed ID | denied and masked where sensitive | 404 | yes |
| any user | missing object | read/download | not found | 404 | yes |
| delegated application | read/edit/submit | no standalone delegation in MVP; company role policy still applies | 200/403/404 | yes on deny |

Delegation note: complex delegation is outside the MVP. Current automated tests
lock the placeholder behavior: no extra application or document access is
granted without an active same-company role or active partner link.
