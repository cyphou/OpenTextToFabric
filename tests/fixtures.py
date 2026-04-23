"""Realistic test fixtures based on actual API responses and BIRT report schemas.

Sources:
- OpenText Content Server REST API v2 (https://developer.opentext.com)
- OpenText Documentum REST Services (https://developer.opentext.com)
- Eclipse BIRT .rptdesign schema v3.2 (https://eclipse-birt.github.io/birt-website/)
- StackOverflow community examples for CS REST API usage
- BIRT Classic Models sample database schema
"""

# ──────────────────────────────────────────────────────────────
# Content Server REST API v2 — Realistic Response Fixtures
# Based on actual /api/v2/nodes endpoints
# ──────────────────────────────────────────────────────────────

CS_AUTH_RESPONSE = {
    "ticket": "LzXvBWfCwRyj0rJY9u6EQTxFDVWDzXYhzGKBgKxpSz8aHQcNejPCX/gGtJaRiML8"
}

CS_AUTH_FAILURE_RESPONSE = {
    "error": "Authentication failed",
    "errorDetail": "Invalid username or password",
    "statusCode": 401,
}

CS_NODE_FOLDER_RESPONSE = {
    "results": {
        "data": {
            "properties": {
                "id": 2000,
                "parent_id": 0,
                "name": "Enterprise Workspace",
                "type": 0,
                "type_name": "Folder",
                "description": "Main enterprise content repository",
                "create_date": "2019-03-15T08:30:00Z",
                "modify_date": "2024-11-20T14:22:33Z",
                "create_user_id": 1000,
                "modify_user_id": 1000,
                "owner_user_id": 1000,
                "owner_group_id": 999,
                "size": 0,
                "size_formatted": "0 Items",
                "mime_type": None,
                "container": True,
                "container_size": 42,
                "reserved": False,
                "reserved_user_id": 0,
                "versions_control_advanced": True,
                "favorite": False,
            }
        }
    }
}

CS_NODE_DOCUMENT_RESPONSE = {
    "results": {
        "data": {
            "properties": {
                "id": 54321,
                "parent_id": 2000,
                "name": "Q4_2024_Financial_Report.pdf",
                "type": 144,
                "type_name": "Document",
                "description": "Quarterly financial summary for FY2024 Q4",
                "create_date": "2024-10-01T09:15:00Z",
                "modify_date": "2024-12-15T16:30:45Z",
                "create_user_id": 1001,
                "modify_user_id": 1002,
                "owner_user_id": 1001,
                "owner_group_id": 999,
                "size": 2457600,
                "size_formatted": "2.34 MB",
                "mime_type": "application/pdf",
                "container": False,
                "container_size": 0,
                "reserved": False,
                "reserved_user_id": 0,
                "versions_control_advanced": True,
                "favorite": True,
                "external_create_date": None,
                "external_modify_date": None,
                "external_source": None,
                "external_identity": None,
                "external_identity_type": None,
            }
        }
    }
}

CS_CHILDREN_RESPONSE = {
    "results": [
        {
            "data": {
                "properties": {
                    "id": 3001,
                    "parent_id": 2000,
                    "name": "Finance",
                    "type": 0,
                    "type_name": "Folder",
                    "description": "Financial documents and reports",
                    "create_date": "2019-05-10T10:00:00Z",
                    "modify_date": "2024-12-01T08:00:00Z",
                    "create_user_id": 1000,
                    "modify_user_id": 1001,
                    "size": 0,
                    "mime_type": "",
                    "container": True,
                    "container_size": 15,
                }
            }
        },
        {
            "data": {
                "properties": {
                    "id": 3002,
                    "parent_id": 2000,
                    "name": "HR Policies",
                    "type": 0,
                    "type_name": "Folder",
                    "description": "Human Resources policy documents",
                    "create_date": "2020-01-15T09:00:00Z",
                    "modify_date": "2024-06-30T17:00:00Z",
                    "create_user_id": 1000,
                    "modify_user_id": 1003,
                    "size": 0,
                    "mime_type": "",
                    "container": True,
                    "container_size": 8,
                }
            }
        },
        {
            "data": {
                "properties": {
                    "id": 54321,
                    "parent_id": 2000,
                    "name": "Q4_2024_Financial_Report.pdf",
                    "type": 144,
                    "type_name": "Document",
                    "description": "Quarterly financial summary",
                    "create_date": "2024-10-01T09:15:00Z",
                    "modify_date": "2024-12-15T16:30:45Z",
                    "create_user_id": 1001,
                    "modify_user_id": 1002,
                    "size": 2457600,
                    "mime_type": "application/pdf",
                    "container": False,
                    "container_size": 0,
                }
            }
        },
        {
            "data": {
                "properties": {
                    "id": 54322,
                    "parent_id": 2000,
                    "name": "Employee_Handbook_v3.docx",
                    "type": 144,
                    "type_name": "Document",
                    "description": "Company employee handbook third edition",
                    "create_date": "2023-06-15T14:30:00Z",
                    "modify_date": "2024-09-01T11:00:00Z",
                    "create_user_id": 1003,
                    "modify_user_id": 1003,
                    "size": 1843200,
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "container": False,
                    "container_size": 0,
                }
            }
        },
        {
            "data": {
                "properties": {
                    "id": 54323,
                    "parent_id": 2000,
                    "name": "Network_Architecture_Diagram.vsdx",
                    "type": 144,
                    "type_name": "Document",
                    "description": "Enterprise network topology diagram",
                    "create_date": "2024-03-20T10:00:00Z",
                    "modify_date": "2024-11-05T09:30:00Z",
                    "create_user_id": 1004,
                    "modify_user_id": 1004,
                    "size": 512000,
                    "mime_type": "application/vnd.ms-visio.drawing.main+xml",
                    "container": False,
                    "container_size": 0,
                }
            }
        },
    ],
    "collection": {
        "paging": {
            "page": 1,
            "limit": 100,
            "total_count": 5,
            "page_total": 1,
            "range_min": 1,
            "range_max": 5,
        }
    },
}

CS_CATEGORIES_RESPONSE = {
    "results": [
        {
            "data": {
                "id": 8001,
                "name": "Document Classification",
                "attributes": {
                    "classification_level": "Confidential",
                    "retention_years": "7",
                    "department": "Finance",
                    "document_type": "Financial Report",
                    "regulatory_reference": "SOX Section 802",
                },
            }
        },
        {
            "data": {
                "id": 8002,
                "name": "Project Metadata",
                "attributes": {
                    "project_code": "PRJ-2024-Q4",
                    "project_name": "FY2024 Year-End Close",
                    "cost_center": "CC-4100",
                    "business_unit": "Corporate Finance",
                    "approval_status": "Approved",
                    "approved_by": "John Smith",
                    "approval_date": "2024-12-10",
                },
            }
        },
    ]
}

CS_PERMISSIONS_RESPONSE = {
    "results": {
        "data": {
            "owner": {
                "right_id": 1001,
                "type": "owner",
                "permissions": [
                    "see", "see_contents", "modify", "edit_attributes",
                    "add_items", "reserve", "add_major_version", "delete_versions",
                    "delete", "edit_permissions",
                ],
            },
            "group": {
                "right_id": 999,
                "type": "group",
                "permissions": ["see", "see_contents"],
            },
            "public": {
                "right_id": None,
                "type": "public",
                "permissions": [],
            },
            "custom": [
                {
                    "right_id": 2001,
                    "name": "Finance_Managers",
                    "type": "group",
                    "permissions": [
                        "see", "see_contents", "modify", "edit_attributes",
                        "add_items", "reserve", "add_major_version",
                    ],
                },
                {
                    "right_id": 2002,
                    "name": "Auditors",
                    "type": "group",
                    "permissions": ["see", "see_contents"],
                },
                {
                    "right_id": 1005,
                    "name": "jane.doe",
                    "type": "user",
                    "permissions": ["see", "see_contents", "modify", "edit_attributes"],
                },
            ],
        }
    }
}

CS_VERSIONS_RESPONSE = {
    "data": [
        {
            "version_number": 1,
            "version_id": 90001,
            "version_number_major": 0,
            "version_number_minor": 1,
            "version_number_name": "0.1",
            "file_name": "Q4_2024_Financial_Report_draft.pdf",
            "file_size": 1200000,
            "file_type": "application/pdf",
            "create_date": "2024-10-01T09:15:00Z",
            "description": "Initial draft",
            "owner_id": 1001,
            "mime_type": "application/pdf",
        },
        {
            "version_number": 2,
            "version_id": 90002,
            "version_number_major": 0,
            "version_number_minor": 2,
            "version_number_name": "0.2",
            "file_name": "Q4_2024_Financial_Report_review.pdf",
            "file_size": 1800000,
            "file_type": "application/pdf",
            "create_date": "2024-11-10T11:30:00Z",
            "description": "Updated with review comments",
            "owner_id": 1002,
            "mime_type": "application/pdf",
        },
        {
            "version_number": 3,
            "version_id": 90003,
            "version_number_major": 1,
            "version_number_minor": 0,
            "version_number_name": "1.0",
            "file_name": "Q4_2024_Financial_Report.pdf",
            "file_size": 2457600,
            "file_type": "application/pdf",
            "create_date": "2024-12-15T16:30:45Z",
            "description": "Final approved version",
            "owner_id": 1001,
            "mime_type": "application/pdf",
        },
    ]
}

CS_WORKFLOW_RESPONSE = {
    "results": [
        {
            "id": 70001,
            "name": "Document_Approval_Workflow",
            "type": "wf_map",
            "status": "completed",
            "start_date": "2024-11-01T09:00:00Z",
            "completion_date": "2024-12-10T17:00:00Z",
            "steps": [
                {
                    "step_id": 1,
                    "name": "Draft Review",
                    "performer_id": 1002,
                    "performer_name": "Jane Doe",
                    "status": "completed",
                    "start_date": "2024-11-01T09:00:00Z",
                    "completion_date": "2024-11-15T14:00:00Z",
                    "disposition": "Approved",
                    "comments": "Good draft, minor formatting changes needed",
                },
                {
                    "step_id": 2,
                    "name": "Manager Approval",
                    "performer_id": 1005,
                    "performer_name": "Bob Johnson",
                    "status": "completed",
                    "start_date": "2024-11-15T14:01:00Z",
                    "completion_date": "2024-12-01T10:00:00Z",
                    "disposition": "Approved",
                    "comments": "Approved pending CFO sign-off",
                },
                {
                    "step_id": 3,
                    "name": "CFO Sign-off",
                    "performer_id": 1006,
                    "performer_name": "Carol Williams",
                    "status": "completed",
                    "start_date": "2024-12-01T10:01:00Z",
                    "completion_date": "2024-12-10T17:00:00Z",
                    "disposition": "Approved",
                    "comments": "",
                },
            ],
        }
    ]
}

CS_MEMBERS_RESPONSE = [
    {
        "id": 1000,
        "name": "Admin",
        "type": 0,
        "first_name": "System",
        "last_name": "Administrator",
        "business_email": "admin@acme-corp.com",
        "group_id": 999,
    },
    {
        "id": 1001,
        "name": "jsmith",
        "type": 0,
        "first_name": "John",
        "last_name": "Smith",
        "business_email": "john.smith@acme-corp.com",
        "group_id": 999,
    },
    {
        "id": 1002,
        "name": "jdoe",
        "type": 0,
        "first_name": "Jane",
        "last_name": "Doe",
        "business_email": "jane.doe@acme-corp.com",
        "group_id": 2001,
    },
    {
        "id": 999,
        "name": "DefaultGroup",
        "type": 1,
        "first_name": "",
        "last_name": "",
        "business_email": "",
        "group_id": 0,
    },
    {
        "id": 2001,
        "name": "Finance_Managers",
        "type": 1,
        "first_name": "",
        "last_name": "",
        "business_email": "finance-managers@acme-corp.com",
        "group_id": 0,
    },
]


# ──────────────────────────────────────────────────────────────
# Documentum REST Services — Realistic Response Fixtures
# Based on Documentum REST API v7.x/16.x format
# ──────────────────────────────────────────────────────────────

DCTM_AUTH_RESPONSE = {
    "properties": {
        "user_name": "dmadmin",
        "user_login_name": "dmadmin",
        "user_source": "inline password",
        "user_privileges": 16,
        "default_folder": "/dmadmin",
        "r_object_id": "0c00000180000100",
    }
}

DCTM_CABINETS_RESPONSE = {
    "id": "https://dctm.acme-corp.com/dctm-rest/repositories/acme_repo/cabinets",
    "title": "Cabinets",
    "author": [{"name": "EMC Documentum"}],
    "updated": "2024-12-20T10:00:00.000+00:00",
    "entries": [
        {
            "id": "https://dctm.acme-corp.com/dctm-rest/repositories/acme_repo/cabinets/0c00000180000200",
            "title": "Enterprise Documents",
            "content": {
                "properties": {
                    "r_object_id": "0c00000180000200",
                    "object_name": "Enterprise Documents",
                    "r_object_type": "dm_cabinet",
                    "title": "Enterprise Document Cabinet",
                    "r_creation_date": "2018-06-01T00:00:00.000+00:00",
                    "r_modify_date": "2024-12-15T14:30:00.000+00:00",
                    "owner_name": "dmadmin",
                    "a_content_type": "",
                    "r_content_size": 0,
                    "r_full_content_size": 0,
                },
            },
            "links": [
                {"rel": "self", "href": "https://dctm.acme-corp.com/dctm-rest/repositories/acme_repo/cabinets/0c00000180000200"},
                {"rel": "edit", "href": "https://dctm.acme-corp.com/dctm-rest/repositories/acme_repo/cabinets/0c00000180000200"},
            ],
        },
        {
            "id": "https://dctm.acme-corp.com/dctm-rest/repositories/acme_repo/cabinets/0c00000180000300",
            "title": "HR & Legal",
            "content": {
                "properties": {
                    "r_object_id": "0c00000180000300",
                    "object_name": "HR & Legal",
                    "r_object_type": "dm_cabinet",
                    "title": "Human Resources and Legal Documents",
                    "r_creation_date": "2018-06-01T00:00:00.000+00:00",
                    "r_modify_date": "2024-11-20T09:00:00.000+00:00",
                    "owner_name": "dmadmin",
                    "a_content_type": "",
                    "r_content_size": 0,
                    "r_full_content_size": 0,
                },
            },
            "links": [
                {"rel": "self", "href": "https://dctm.acme-corp.com/dctm-rest/repositories/acme_repo/cabinets/0c00000180000300"},
            ],
        },
    ],
    "links": [
        {"rel": "self", "href": "https://dctm.acme-corp.com/dctm-rest/repositories/acme_repo/cabinets"},
    ],
}

DCTM_DQL_FOLDER_CONTENTS = {
    "id": "https://dctm.acme-corp.com/dctm-rest/repositories/acme_repo/dql",
    "entries": [
        {
            "content": {
                "properties": {
                    "r_object_id": "0900000180001001",
                    "object_name": "2024_Annual_Report.pdf",
                    "r_object_type": "dm_document",
                    "r_content_size": 4500000,
                    "a_content_type": "application/pdf",
                    "r_creation_date": "2024-01-15T10:00:00.000+00:00",
                    "r_modify_date": "2024-12-01T15:30:00.000+00:00",
                    "owner_name": "jsmith",
                    "r_version_label": ["1.0", "CURRENT"],
                    "r_lock_owner": "",
                }
            }
        },
        {
            "content": {
                "properties": {
                    "r_object_id": "0900000180001002",
                    "object_name": "Contract_Template_NDA.docx",
                    "r_object_type": "dm_document",
                    "r_content_size": 156000,
                    "a_content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "r_creation_date": "2023-05-20T09:00:00.000+00:00",
                    "r_modify_date": "2024-08-10T11:00:00.000+00:00",
                    "owner_name": "legal_admin",
                    "r_version_label": ["2.1", "CURRENT"],
                    "r_lock_owner": "",
                }
            }
        },
        {
            "content": {
                "properties": {
                    "r_object_id": "0b00000180002001",
                    "object_name": "Compliance",
                    "r_object_type": "dm_folder",
                    "r_content_size": 0,
                    "a_content_type": "",
                    "r_creation_date": "2020-03-01T08:00:00.000+00:00",
                    "r_modify_date": "2024-11-30T16:00:00.000+00:00",
                    "owner_name": "dmadmin",
                    "r_version_label": [],
                    "r_lock_owner": "",
                }
            }
        },
    ],
}

DCTM_ACL_DQL_RESPONSE = {
    "entries": [
        {
            "content": {
                "properties": {
                    "r_accessor_name": "dm_world",
                    "r_accessor_permit": 3,
                    "r_accessor_xpermit": 0,
                    "r_is_group": True,
                }
            }
        },
        {
            "content": {
                "properties": {
                    "r_accessor_name": "dm_owner",
                    "r_accessor_permit": 7,
                    "r_accessor_xpermit": 3,
                    "r_is_group": False,
                }
            }
        },
        {
            "content": {
                "properties": {
                    "r_accessor_name": "finance_group",
                    "r_accessor_permit": 6,
                    "r_accessor_xpermit": 0,
                    "r_is_group": True,
                }
            }
        },
        {
            "content": {
                "properties": {
                    "r_accessor_name": "external_auditors",
                    "r_accessor_permit": 3,
                    "r_accessor_xpermit": 0,
                    "r_is_group": True,
                }
            }
        },
    ]
}

DCTM_LIFECYCLE_DQL_RESPONSE = {
    "entries": [
        {
            "content": {
                "properties": {
                    "r_policy_id": "4600000180000001",
                    "r_current_state": 2,
                }
            }
        }
    ]
}

DCTM_RENDITIONS_DQL_RESPONSE = {
    "entries": [
        {
            "content": {
                "properties": {
                    "r_object_id": "0600000180005001",
                    "full_format": "pdf",
                    "r_content_size": 4500000,
                }
            }
        },
        {
            "content": {
                "properties": {
                    "r_object_id": "0600000180005002",
                    "full_format": "jpeg",
                    "r_content_size": 45000,
                }
            }
        },
    ]
}


# ──────────────────────────────────────────────────────────────
# BIRT .rptdesign — Realistic Report XML
# Based on BIRT 4.x schema, Classic Models sample database
# ──────────────────────────────────────────────────────────────

BIRT_CLASSIC_MODELS_REPORT = """<?xml version="1.0" encoding="UTF-8"?>
<report version="3.2.23" id="1">
    <property name="createdBy">Eclipse BIRT Designer Version 4.8.0</property>
    <property name="units">in</property>
    <property name="iconFile">/templates/blank_report.gif</property>
    <property name="bidiLayoutOrientation">ltr</property>
    <property name="imageDPI">96</property>

    <data-sources>
        <oda-data-source extensionID="org.eclipse.birt.report.data.oda.jdbc" name="Classic Models" id="100">
            <property name="odaDriverClass">com.mysql.jdbc.Driver</property>
            <property name="odaURL">jdbc:mysql://localhost:3306/classicmodels</property>
            <property name="odaUser">root</property>
            <property name="odaPassword">el:UjOxMWMzOC1jNzI3LTQ0YjMtYjU5MC01MDc=</property>
            <property name="odaJndiName"></property>
        </oda-data-source>
        <oda-data-source extensionID="org.eclipse.birt.report.data.oda.jdbc" name="Oracle DWH" id="101">
            <property name="odaDriverClass">oracle.jdbc.OracleDriver</property>
            <property name="odaURL">jdbc:oracle:thin:@warehouse.acme-corp.com:1521:DWPROD</property>
            <property name="odaUser">report_user</property>
        </oda-data-source>
    </data-sources>

    <data-sets>
        <oda-data-set extensionID="org.eclipse.birt.report.data.oda.jdbc.JdbcSelectDataSet" name="OrdersByCustomer" id="200">
            <property name="dataSource">Classic Models</property>
            <list-property name="columnHints">
                <structure>
                    <property name="columnName">customerName</property>
                    <property name="alias">customerName</property>
                    <property name="dataType">string</property>
                </structure>
                <structure>
                    <property name="columnName">orderNumber</property>
                    <property name="alias">orderNumber</property>
                    <property name="dataType">integer</property>
                </structure>
                <structure>
                    <property name="columnName">orderDate</property>
                    <property name="alias">orderDate</property>
                    <property name="dataType">date</property>
                </structure>
                <structure>
                    <property name="columnName">status</property>
                    <property name="alias">status</property>
                    <property name="dataType">string</property>
                </structure>
                <structure>
                    <property name="columnName">quantityOrdered</property>
                    <property name="alias">quantityOrdered</property>
                    <property name="dataType">integer</property>
                </structure>
                <structure>
                    <property name="columnName">priceEach</property>
                    <property name="alias">priceEach</property>
                    <property name="dataType">decimal</property>
                </structure>
                <structure>
                    <property name="columnName">productLine</property>
                    <property name="alias">productLine</property>
                    <property name="dataType">string</property>
                </structure>
                <structure>
                    <property name="columnName">country</property>
                    <property name="alias">country</property>
                    <property name="dataType">string</property>
                </structure>
            </list-property>
            <list-property name="computedColumns">
                <structure>
                    <property name="name">lineTotal</property>
                    <property name="dataType">float</property>
                    <expression name="expression" type="javascript">row["quantityOrdered"] * row["priceEach"]</expression>
                </structure>
                <structure>
                    <property name="name">orderYear</property>
                    <property name="dataType">integer</property>
                    <expression name="expression" type="javascript">BirtDateTime.year(row["orderDate"])</expression>
                </structure>
                <structure>
                    <property name="name">orderQuarter</property>
                    <property name="dataType">string</property>
                    <expression name="expression" type="javascript">
                        "Q" + BirtDateTime.quarter(row["orderDate"])
                    </expression>
                </structure>
                <structure>
                    <property name="name">discountedPrice</property>
                    <property name="dataType">float</property>
                    <expression name="expression" type="javascript">
                        row["quantityOrdered"] > 50 ? row["priceEach"] * 0.9 : row["priceEach"]
                    </expression>
                </structure>
            </list-property>
            <list-property name="parameters">
                <structure>
                    <property name="name">paramStartDate</property>
                    <property name="nativeName"></property>
                    <property name="dataType">date</property>
                    <property name="nativeDataType">91</property>
                    <property name="position">1</property>
                    <property name="isInput">true</property>
                    <property name="isOutput">false</property>
                </structure>
                <structure>
                    <property name="name">paramEndDate</property>
                    <property name="nativeName"></property>
                    <property name="dataType">date</property>
                    <property name="nativeDataType">91</property>
                    <property name="position">2</property>
                    <property name="isInput">true</property>
                    <property name="isOutput">false</property>
                </structure>
            </list-property>
            <property name="queryText">
                SELECT c.customerName, o.orderNumber, o.orderDate, o.status,
                       od.quantityOrdered, od.priceEach, p.productLine, c.country
                FROM customers c
                JOIN orders o ON c.customerNumber = o.customerNumber
                JOIN orderdetails od ON o.orderNumber = od.orderNumber
                JOIN products p ON od.productCode = p.productCode
                WHERE o.orderDate BETWEEN ? AND ?
                ORDER BY c.customerName, o.orderDate DESC
            </property>
        </oda-data-set>

        <oda-data-set extensionID="org.eclipse.birt.report.data.oda.jdbc.JdbcSelectDataSet" name="SalesSummary" id="201">
            <property name="dataSource">Oracle DWH</property>
            <list-property name="columnHints">
                <structure>
                    <property name="columnName">region</property>
                    <property name="dataType">string</property>
                </structure>
                <structure>
                    <property name="columnName">total_revenue</property>
                    <property name="dataType">decimal</property>
                </structure>
                <structure>
                    <property name="columnName">order_count</property>
                    <property name="dataType">integer</property>
                </structure>
                <structure>
                    <property name="columnName">avg_order_value</property>
                    <property name="dataType">decimal</property>
                </structure>
            </list-property>
            <list-property name="computedColumns">
                <structure>
                    <property name="name">revenueFormatted</property>
                    <property name="dataType">string</property>
                    <expression name="expression" type="javascript">
                        BirtStr.concat("$", BirtStr.left(row["total_revenue"].toString(), 10))
                    </expression>
                </structure>
            </list-property>
            <property name="queryText">
                SELECT r.region_name AS region,
                       SUM(s.amount) AS total_revenue,
                       COUNT(s.order_id) AS order_count,
                       AVG(s.amount) AS avg_order_value
                FROM sales_fact s
                JOIN region_dim r ON s.region_id = r.region_id
                GROUP BY r.region_name
                ORDER BY total_revenue DESC
            </property>
        </oda-data-set>
    </data-sets>

    <parameters>
        <scalar-parameter name="ReportStartDate" id="300">
            <property name="valueType">static</property>
            <property name="dataType">date</property>
            <property name="distinct">true</property>
            <property name="isRequired">true</property>
            <property name="controlType">text-box</property>
            <property name="promptText">Start Date (yyyy-MM-dd)</property>
            <property name="format">yyyy-MM-dd</property>
            <property name="defaultValue">2024-01-01</property>
        </scalar-parameter>
        <scalar-parameter name="ReportEndDate" id="301">
            <property name="valueType">static</property>
            <property name="dataType">date</property>
            <property name="distinct">true</property>
            <property name="isRequired">true</property>
            <property name="controlType">text-box</property>
            <property name="promptText">End Date (yyyy-MM-dd)</property>
            <property name="format">yyyy-MM-dd</property>
            <property name="defaultValue">2024-12-31</property>
        </scalar-parameter>
        <scalar-parameter name="ProductLineFilter" id="302">
            <property name="valueType">static</property>
            <property name="dataType">string</property>
            <property name="controlType">list-box</property>
            <property name="isRequired">false</property>
            <property name="promptText">Filter by Product Line</property>
            <property name="defaultValue">All</property>
            <list-property name="selectionList">
                <structure>
                    <property name="value">All</property>
                    <property name="label">All Product Lines</property>
                </structure>
                <structure>
                    <property name="value">Classic Cars</property>
                    <property name="label">Classic Cars</property>
                </structure>
                <structure>
                    <property name="value">Motorcycles</property>
                    <property name="label">Motorcycles</property>
                </structure>
                <structure>
                    <property name="value">Planes</property>
                    <property name="label">Planes</property>
                </structure>
                <structure>
                    <property name="value">Ships</property>
                    <property name="label">Ships</property>
                </structure>
                <structure>
                    <property name="value">Trains</property>
                    <property name="label">Trains</property>
                </structure>
                <structure>
                    <property name="value">Trucks and Buses</property>
                    <property name="label">Trucks and Buses</property>
                </structure>
                <structure>
                    <property name="value">Vintage Cars</property>
                    <property name="label">Vintage Cars</property>
                </structure>
            </list-property>
        </scalar-parameter>
    </parameters>

    <styles>
        <style name="report-header">
            <property name="fontFamily">Arial</property>
            <property name="fontSize">18pt</property>
            <property name="fontWeight">bold</property>
            <property name="color">#003366</property>
            <property name="textAlign">center</property>
            <property name="borderBottomStyle">solid</property>
            <property name="borderBottomWidth">2px</property>
            <property name="borderBottomColor">#003366</property>
            <property name="paddingBottom">8pt</property>
            <property name="marginBottom">12pt</property>
        </style>
        <style name="table-header">
            <property name="fontFamily">Arial</property>
            <property name="fontSize">9pt</property>
            <property name="fontWeight">bold</property>
            <property name="backgroundColor">#003366</property>
            <property name="color">#FFFFFF</property>
            <property name="textAlign">center</property>
            <property name="paddingTop">4pt</property>
            <property name="paddingBottom">4pt</property>
        </style>
        <style name="table-detail">
            <property name="fontFamily">Arial</property>
            <property name="fontSize">8pt</property>
            <property name="borderBottomStyle">solid</property>
            <property name="borderBottomWidth">thin</property>
            <property name="borderBottomColor">#CCCCCC</property>
            <property name="paddingTop">2pt</property>
            <property name="paddingBottom">2pt</property>
        </style>
        <style name="group-header">
            <property name="fontFamily">Arial</property>
            <property name="fontSize">11pt</property>
            <property name="fontWeight">bold</property>
            <property name="backgroundColor">#E0E8F0</property>
            <property name="paddingTop">4pt</property>
            <property name="paddingBottom">4pt</property>
            <property name="paddingLeft">6pt</property>
        </style>
        <style name="currency">
            <property name="numberFormat">$#,##0.00</property>
            <property name="textAlign">right</property>
        </style>
    </styles>

    <page-setup>
        <simple-master-page name="Simple MasterPage" id="2">
            <property name="type">custom</property>
            <property name="height">11in</property>
            <property name="width">8.5in</property>
            <property name="topMargin">0.5in</property>
            <property name="leftMargin">0.75in</property>
            <property name="bottomMargin">0.5in</property>
            <property name="rightMargin">0.75in</property>
            <page-header>
                <grid name="HeaderGrid" id="3">
                    <column id="4"/>
                    <row id="5">
                        <cell id="6">
                            <label id="7">
                                <text-property name="text">Acme Corporation - Classic Models Division</text-property>
                            </label>
                        </cell>
                    </row>
                </grid>
            </page-header>
            <page-footer>
                <text id="8">
                    <property name="textAlign">center</property>
                    <property name="fontSize">7pt</property>
                    <text-property name="content"><![CDATA[Page <value-of>pageNumber</value-of> of <value-of>totalPage</value-of> — Confidential]]></text-property>
                </text>
            </page-footer>
        </simple-master-page>
    </page-setup>

    <body>
        <label name="ReportTitle" id="10">
            <property name="style">report-header</property>
            <text-property name="text">Orders by Customer &amp; Product Line</text-property>
        </label>

        <text name="ReportSubtitle" id="11">
            <property name="fontFamily">Arial</property>
            <property name="fontSize">10pt</property>
            <property name="color">#666666</property>
            <property name="textAlign">center</property>
            <property name="marginBottom">16pt</property>
            <text-property name="content"><![CDATA[Report Period: <value-of>params["ReportStartDate"].value</value-of> to <value-of>params["ReportEndDate"].value</value-of>]]></text-property>
        </text>

        <table name="OrdersTable" id="20">
            <property name="dataSet">OrdersByCustomer</property>
            <property name="style">table-detail</property>
            <property name="width">100%</property>
            <list-property name="boundDataColumns">
                <structure>
                    <property name="name">customerName</property>
                    <expression name="expression" type="javascript">dataSetRow["customerName"]</expression>
                    <property name="dataType">string</property>
                </structure>
                <structure>
                    <property name="name">orderNumber</property>
                    <expression name="expression" type="javascript">dataSetRow["orderNumber"]</expression>
                    <property name="dataType">integer</property>
                </structure>
                <structure>
                    <property name="name">orderDate</property>
                    <expression name="expression" type="javascript">dataSetRow["orderDate"]</expression>
                    <property name="dataType">date</property>
                </structure>
                <structure>
                    <property name="name">status</property>
                    <expression name="expression" type="javascript">dataSetRow["status"]</expression>
                    <property name="dataType">string</property>
                </structure>
                <structure>
                    <property name="name">productLine</property>
                    <expression name="expression" type="javascript">dataSetRow["productLine"]</expression>
                    <property name="dataType">string</property>
                </structure>
                <structure>
                    <property name="name">lineTotal</property>
                    <expression name="expression" type="javascript">dataSetRow["lineTotal"]</expression>
                    <property name="dataType">float</property>
                </structure>
                <structure>
                    <property name="name">orderQuarter</property>
                    <expression name="expression" type="javascript">dataSetRow["orderQuarter"]</expression>
                    <property name="dataType">string</property>
                </structure>
                <structure>
                    <property name="name">totalRevenue</property>
                    <expression name="expression" type="javascript">Total.sum(row["lineTotal"])</expression>
                    <property name="dataType">float</property>
                </structure>
                <structure>
                    <property name="name">orderCount</property>
                    <expression name="expression" type="javascript">Total.countDistinct(row["orderNumber"])</expression>
                    <property name="dataType">integer</property>
                </structure>
                <structure>
                    <property name="name">avgOrderValue</property>
                    <expression name="expression" type="javascript">Total.ave(row["lineTotal"])</expression>
                    <property name="dataType">float</property>
                </structure>
                <structure>
                    <property name="name">pctOfTotal</property>
                    <expression name="expression" type="javascript">Total.percentSum(row["lineTotal"])</expression>
                    <property name="dataType">float</property>
                </structure>
                <structure>
                    <property name="name">runningTotal</property>
                    <expression name="expression" type="javascript">Total.runningSum(row["lineTotal"])</expression>
                    <property name="dataType">float</property>
                </structure>
            </list-property>
            <column id="21"/>
            <column id="22"/>
            <column id="23"/>
            <column id="24"/>
            <column id="25"/>
            <column id="26"/>
            <group name="CustomerGroup" id="30">
                <expression name="keyExpr" type="javascript">row["customerName"]</expression>
                <property name="style">group-header</property>
            </group>
        </table>

        <extended-item name="SalesChart" id="40">
            <property name="extensionName">Chart</property>
            <property name="width">700px</property>
            <property name="height">400px</property>
            <xml-property name="xmlRepresentation"><![CDATA[
<Chart version="2.6.0">
  <Type>Bar</Type>
  <SubType>Side-by-side</SubType>
  <Dimension>Two_Dimensional</Dimension>
  <Title>
    <Label><Caption>Revenue by Product Line</Caption></Label>
    <Visible>true</Visible>
  </Title>
  <Legend>
    <Position>Right</Position>
    <Visible>true</Visible>
  </Legend>
  <Axes>
    <Axis type="Category" orientation="Horizontal">
      <Title><Caption>Product Line</Caption></Title>
    </Axis>
    <Axis type="Linear" orientation="Vertical">
      <Title><Caption>Revenue ($)</Caption></Title>
      <FormatSpecifier pattern="$#,##0"/>
    </Axis>
  </Axes>
  <Series>
    <Definition>
      <Query>row["productLine"]</Query>
    </Definition>
    <Definition>
      <Query>row["lineTotal"]</Query>
      <Grouping>
        <AggregateExpression>Sum</AggregateExpression>
      </Grouping>
    </Definition>
  </Series>
</Chart>]]></xml-property>
        </extended-item>

        <extended-item name="SalesPieChart" id="41">
            <property name="extensionName">Chart</property>
            <property name="width">500px</property>
            <property name="height">400px</property>
            <xml-property name="xmlRepresentation"><![CDATA[
<Chart version="2.6.0">
  <Type>Pie</Type>
  <Dimension>Two_Dimensional_With_Depth</Dimension>
  <Title>
    <Label><Caption>Revenue Distribution by Region</Caption></Label>
  </Title>
  <Series>
    <Definition>
      <Query>row["country"]</Query>
    </Definition>
    <Definition>
      <Query>row["lineTotal"]</Query>
      <Grouping>
        <AggregateExpression>Sum</AggregateExpression>
      </Grouping>
    </Definition>
  </Series>
</Chart>]]></xml-property>
        </extended-item>

        <extended-item name="SalesLineChart" id="42">
            <property name="extensionName">Chart</property>
            <property name="width">700px</property>
            <property name="height">350px</property>
            <xml-property name="xmlRepresentation"><![CDATA[
<Chart version="2.6.0">
  <Type>Line</Type>
  <Dimension>Two_Dimensional</Dimension>
  <Title>
    <Label><Caption>Monthly Revenue Trend</Caption></Label>
  </Title>
</Chart>]]></xml-property>
        </extended-item>

        <extended-item name="QuarterlyCrosstab" id="50">
            <property name="extensionName">Crosstab</property>
            <property name="width">100%</property>
            <xml-property name="xmlRepresentation"><![CDATA[
<Crosstab>
  <Rows>
    <Dimension name="productLine"/>
  </Rows>
  <Columns>
    <Dimension name="orderQuarter"/>
  </Columns>
  <Measures>
    <Measure name="lineTotal" aggregation="Sum"/>
    <Measure name="orderCount" aggregation="Count"/>
  </Measures>
</Crosstab>]]></xml-property>
        </extended-item>

        <grid name="SummaryGrid" id="60">
            <property name="marginTop">24pt</property>
            <column id="61"/>
            <column id="62"/>
            <row id="63">
                <cell id="64">
                    <label name="SummaryLabel" id="65">
                        <property name="fontFamily">Arial</property>
                        <property name="fontSize">12pt</property>
                        <property name="fontWeight">bold</property>
                        <text-property name="text">Summary Statistics</text-property>
                    </label>
                </cell>
                <cell id="66">
                    <data name="GeneratedDate" id="67">
                        <property name="fontFamily">Arial</property>
                        <property name="fontSize">8pt</property>
                        <property name="color">#999999</property>
                        <property name="textAlign">right</property>
                        <expression name="expression" type="javascript">BirtDateTime.now()</expression>
                    </data>
                </cell>
            </row>
        </grid>

        <image name="CompanyLogo" id="70">
            <property name="source">url</property>
            <expression name="uri" type="javascript">"https://acme-corp.com/images/logo.png"</expression>
        </image>
    </body>
</report>
"""

# ──────────────────────────────────────────────────────────────
# Real BIRT Expressions — comprehensive test cases
# ──────────────────────────────────────────────────────────────

BIRT_EXPRESSION_TEST_CASES = [
    # Aggregation functions
    {"birt": 'Total.sum(row["lineTotal"])', "expected_dax": "SUM([lineTotal])", "category": "aggregation"},
    {"birt": "Total.count()", "expected_dax": "COUNTROWS()", "category": "aggregation"},
    {"birt": 'Total.count(row["orderNumber"])', "expected_dax": "COUNT([orderNumber])", "category": "aggregation"},
    {"birt": 'Total.ave(row["priceEach"])', "expected_dax": "AVERAGE([priceEach])", "category": "aggregation"},
    {"birt": 'Total.max(row["lineTotal"])', "expected_dax": "MAX([lineTotal])", "category": "aggregation"},
    {"birt": 'Total.min(row["priceEach"])', "expected_dax": "MIN([priceEach])", "category": "aggregation"},
    {"birt": 'Total.countDistinct(row["customerName"])', "expected_dax": "DISTINCTCOUNT([customerName])", "category": "aggregation"},
    {"birt": 'Total.percentSum(row["lineTotal"])', "expected_dax_contains": "DIVIDE", "category": "aggregation"},
    {"birt": 'Total.runningSum(row["lineTotal"])', "expected_dax_contains": "CALCULATE", "category": "aggregation"},
    {"birt": 'Total.rank(row["lineTotal"])', "expected_dax_contains": "RANKX", "category": "aggregation"},
    {"birt": 'Total.variance(row["priceEach"])', "expected_dax_contains": "VAR.S", "category": "aggregation"},
    {"birt": 'Total.stdDev(row["priceEach"])', "expected_dax_contains": "STDEV.S", "category": "aggregation"},

    # String functions
    {"birt": 'BirtStr.toUpper(row["customerName"])', "expected_dax": "UPPER([customerName])", "category": "string"},
    {"birt": 'BirtStr.toLower(row["status"])', "expected_dax": "LOWER([status])", "category": "string"},
    {"birt": 'BirtStr.trim(row["country"])', "expected_dax": "TRIM([country])", "category": "string"},
    {"birt": 'BirtStr.left(row["productCode"], 3)', "expected_dax": "LEFT([productCode], 3)", "category": "string"},
    {"birt": 'BirtStr.right(row["productCode"], 4)', "expected_dax": "RIGHT([productCode], 4)", "category": "string"},
    {"birt": 'BirtStr.length(row["customerName"])', "expected_dax": "LEN([customerName])", "category": "string"},

    # Date/time functions
    {"birt": "BirtDateTime.now()", "expected_dax": "NOW()", "category": "datetime"},
    {"birt": "BirtDateTime.today()", "expected_dax": "TODAY()", "category": "datetime"},
    {"birt": 'BirtDateTime.year(row["orderDate"])', "expected_dax": "YEAR([orderDate])", "category": "datetime"},
    {"birt": 'BirtDateTime.month(row["orderDate"])', "expected_dax": "MONTH([orderDate])", "category": "datetime"},
    {"birt": 'BirtDateTime.day(row["orderDate"])', "expected_dax": "DAY([orderDate])", "category": "datetime"},
    {"birt": 'BirtDateTime.quarter(row["orderDate"])', "expected_dax": "QUARTER([orderDate])", "category": "datetime"},

    # Math functions
    {"birt": 'BirtMath.round(row["priceEach"], 2)', "expected_dax": "ROUND([priceEach], 2)", "category": "math"},
    {"birt": 'BirtMath.abs(row["profitMargin"])', "expected_dax": "ABS([profitMargin])", "category": "math"},
    {"birt": 'BirtMath.ceiling(row["total"])', "expected_dax_contains": "CEILING", "category": "math"},
    {"birt": 'BirtMath.floor(row["total"])', "expected_dax_contains": "FLOOR", "category": "math"},

    # Row/dataSetRow references
    {"birt": 'row["lineTotal"]', "expected_dax": "[lineTotal]", "category": "reference"},
    {"birt": 'dataSetRow["customerName"]', "expected_dax": "[customerName]", "category": "reference"},
    {"birt": 'params["ReportStartDate"].value', "expected_dax": "[@ReportStartDate]", "category": "parameter"},

    # Ternary / conditional
    {"birt": 'row["quantityOrdered"] > 50 ? row["priceEach"] * 0.9 : row["priceEach"]', "expected_dax_contains": "IF(", "category": "conditional"},
    {"birt": 'row["status"] == "Shipped" ? "Complete" : "Pending"', "expected_dax_contains": "IF(", "category": "conditional"},

    # Operators
    {"birt": 'row["amount"] == 0', "expected_dax_not_contains": "==", "category": "operator"},
    {"birt": 'row["status"] !== "cancelled"', "expected_dax_contains": "<>", "category": "operator"},

    # Computed column expressions (complex)
    {"birt": 'row["quantityOrdered"] * row["priceEach"]', "expected_dax": "[quantityOrdered] * [priceEach]", "category": "computed"},
]


# ──────────────────────────────────────────────────────────────
# Real-world Governance / Permission mapping fixtures
# ──────────────────────────────────────────────────────────────

REALISTIC_CS_PERMISSIONS = [
    {
        "node_id": 54321,
        "entries": [
            {"type": "owner", "name": "jsmith", "right_id": 1001,
             "permissions": ["see", "see_contents", "modify", "edit_attributes", "add_items",
                             "reserve", "add_major_version", "delete_versions", "delete", "edit_permissions"]},
            {"type": "custom", "name": "Finance_Managers", "right_id": 2001,
             "permissions": ["see", "see_contents", "modify", "edit_attributes", "add_items", "reserve"]},
            {"type": "custom", "name": "Auditors", "right_id": 2002,
             "permissions": ["see", "see_contents"]},
            {"type": "custom", "name": "jdoe", "right_id": 1002,
             "permissions": ["see", "see_contents", "modify"]},
            {"type": "group", "name": "DefaultGroup", "right_id": 999,
             "permissions": ["see"]},
        ],
    },
    {
        "node_id": 54322,
        "entries": [
            {"type": "owner", "name": "legal_admin", "right_id": 1010,
             "permissions": ["see", "see_contents", "modify", "edit_attributes", "delete", "edit_permissions"]},
            {"type": "custom", "name": "Legal_Team", "right_id": 2003,
             "permissions": ["see", "see_contents", "modify", "edit_attributes"]},
            {"type": "custom", "name": "HR_Managers", "right_id": 2004,
             "permissions": ["see", "see_contents"]},
        ],
    },
]

REALISTIC_DCTM_PERMISSIONS = [
    {
        "object_id": "0900000180001001",
        "acl_entries": [
            {"r_accessor_name": "dm_world", "r_accessor_permit": 3, "r_is_group": True},
            {"r_accessor_name": "dm_owner", "r_accessor_permit": 7, "r_is_group": False},
            {"r_accessor_name": "finance_group", "r_accessor_permit": 6, "r_is_group": True},
            {"r_accessor_name": "external_auditors", "r_accessor_permit": 3, "r_is_group": True},
            {"r_accessor_name": "cfo_user", "r_accessor_permit": 7, "r_is_group": False},
        ],
    },
    {
        "object_id": "0900000180001002",
        "acl_entries": [
            {"r_accessor_name": "legal_group", "r_accessor_permit": 6, "r_is_group": True},
            {"r_accessor_name": "hr_managers", "r_accessor_permit": 4, "r_is_group": True},
            {"r_accessor_name": "compliance_officer", "r_accessor_permit": 3, "r_is_group": False},
        ],
    },
]

REALISTIC_GROUP_MAPPING = {
    "Finance_Managers": "FinanceManagers@acme-corp.com",
    "Auditors": "Auditors@acme-corp.com",
    "Legal_Team": "LegalTeam@acme-corp.com",
    "HR_Managers": "HRManagers@acme-corp.com",
    "DefaultGroup": "AllEmployees@acme-corp.com",
    "finance_group": "FinanceManagers@acme-corp.com",
    "external_auditors": "ExternalAuditors@acme-corp.com",
    "legal_group": "LegalTeam@acme-corp.com",
    "hr_managers": "HRManagers@acme-corp.com",
    "dm_world": "AllEmployees@acme-corp.com",
}

REALISTIC_USER_MAPPING = {
    "jsmith": "john.smith@acme-corp.com",
    "jdoe": "jane.doe@acme-corp.com",
    "legal_admin": "legal.admin@acme-corp.com",
    "dm_owner": "content.owner@acme-corp.com",
    "cfo_user": "carol.williams@acme-corp.com",
    "compliance_officer": "compliance@acme-corp.com",
}


# ──────────────────────────────────────────────────────────────
# Real-world metadata for classification mapping
# ──────────────────────────────────────────────────────────────

REALISTIC_METADATA = [
    {
        "node_id": 54321,
        "categories": [
            {
                "category_id": 8001,
                "category_name": "Document Classification",
                "attributes": {
                    "classification_level": "Confidential",
                    "retention_years": "7",
                    "department": "Finance",
                },
            },
        ],
    },
    {
        "node_id": 54322,
        "categories": [
            {
                "category_id": 8001,
                "category_name": "Document Classification",
                "attributes": {
                    "classification_level": "Internal",
                    "retention_years": "5",
                    "department": "HR",
                },
            },
        ],
    },
    {
        "node_id": 54323,
        "categories": [
            {
                "category_id": 8001,
                "category_name": "Document Classification",
                "attributes": {
                    "classification_level": "Public",
                    "retention_years": "3",
                    "department": "IT",
                },
            },
        ],
    },
]


# ──────────────────────────────────────────────────────────────
# Real-world document version chains
# ──────────────────────────────────────────────────────────────

REALISTIC_VERSION_DOCS = [
    {
        "node_id": 54321,
        "versions": [
            {"version_number": 1, "version_id": 90001, "create_date": "2024-10-01T09:15:00Z",
             "file_size": 1200000, "created_by": "jsmith", "mime_type": "application/pdf",
             "description": "Initial draft"},
            {"version_number": 2, "version_id": 90002, "create_date": "2024-11-10T11:30:00Z",
             "file_size": 1800000, "created_by": "jdoe", "mime_type": "application/pdf",
             "description": "Updated with review comments"},
            {"version_number": 3, "version_id": 90003, "create_date": "2024-12-15T16:30:45Z",
             "file_size": 2457600, "created_by": "jsmith", "mime_type": "application/pdf",
             "description": "Final approved version"},
        ],
    },
    {
        "node_id": 54322,
        "versions": [
            {"version_number": 1, "version_id": 91001, "create_date": "2023-06-15T14:30:00Z",
             "file_size": 1500000, "created_by": "legal_admin", "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "description": "First edition"},
            {"version_number": 2, "version_id": 91002, "create_date": "2024-01-20T10:00:00Z",
             "file_size": 1650000, "created_by": "legal_admin", "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "description": "Updated for 2024 compliance changes"},
            {"version_number": 3, "version_id": 91003, "create_date": "2024-09-01T11:00:00Z",
             "file_size": 1843200, "created_by": "legal_admin", "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "description": "Third edition with new benefits section"},
        ],
    },
]

# ──────────────────────────────────────────────────────────────
# Real-world rendition fixtures
# ──────────────────────────────────────────────────────────────

REALISTIC_RENDITION_DOCS_CS = [
    {
        "node_id": 54321,
        "versions": [
            {"mime_type": "application/pdf", "file_size": 2457600},
        ],
    },
    {
        "node_id": 54322,
        "versions": [
            {"mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "file_size": 1843200},
        ],
    },
    {
        "node_id": 54323,
        "versions": [
            {"mime_type": "application/vnd.ms-visio.drawing.main+xml", "file_size": 512000},
        ],
    },
]

REALISTIC_RENDITION_DOCS_DCTM = [
    {
        "object_id": "0900000180001001",
        "renditions": [
            {"full_format": "pdf", "r_content_size": 4500000},
            {"full_format": "jpeg", "r_content_size": 45000},
        ],
    },
    {
        "object_id": "0900000180001002",
        "renditions": [
            {"full_format": "pdf", "r_content_size": 200000},
            {"full_format": "msw12", "r_content_size": 156000},
        ],
    },
]


# ──────────────────────────────────────────────────────────────
# JDBC Connection Strings — real-world patterns
# ──────────────────────────────────────────────────────────────

REALISTIC_JDBC_CONNECTIONS = [
    {
        "name": "Oracle Production",
        "odaDriverClass": "oracle.jdbc.OracleDriver",
        "odaURL": "jdbc:oracle:thin:@dbprod.acme-corp.com:1521:ORCL",
        "odaUser": "report_readonly",
    },
    {
        "name": "PostgreSQL Analytics",
        "odaDriverClass": "org.postgresql.Driver",
        "odaURL": "jdbc:postgresql://analytics.acme-corp.com:5432/warehouse",
        "odaUser": "bi_reader",
    },
    {
        "name": "SQL Server ERP",
        "odaDriverClass": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
        "odaURL": "jdbc:sqlserver://erp.acme-corp.com:1433;databaseName=ERP_Prod;encrypt=true",
        "odaUser": "svc_reporting",
    },
    {
        "name": "MySQL Legacy",
        "odaDriverClass": "com.mysql.jdbc.Driver",
        "odaURL": "jdbc:mysql://legacy-db.acme-corp.com:3306/classicmodels?useSSL=true",
        "odaUser": "root",
    },
]

REALISTIC_DATASETS_FOR_M_QUERY = [
    {
        "name": "CustomerOrders",
        "data_source": "Oracle Production",
        "query": """SELECT c.customer_name, o.order_id, o.order_date, o.total_amount,
                           p.product_name, od.quantity, od.unit_price
                    FROM customers c
                    JOIN orders o ON c.customer_id = o.customer_id
                    JOIN order_details od ON o.order_id = od.order_id
                    JOIN products p ON od.product_id = p.product_id
                    WHERE o.order_date >= SYSDATE - 365""",
    },
    {
        "name": "SalesSummaryByRegion",
        "data_source": "PostgreSQL Analytics",
        "query": """SELECT r.region_name, SUM(s.amount) AS total_sales,
                           COUNT(DISTINCT s.customer_id) AS customer_count,
                           AVG(s.amount) AS avg_sale
                    FROM sales s
                    JOIN regions r ON s.region_id = r.region_id
                    GROUP BY r.region_name
                    ORDER BY total_sales DESC""",
    },
    {
        "name": "InventoryLevels",
        "data_source": "SQL Server ERP",
        "query": """SELECT p.product_code, p.product_name, p.category,
                           i.quantity_on_hand, i.reorder_level, i.last_restock_date
                    FROM Products p
                    JOIN Inventory i ON p.product_id = i.product_id
                    WHERE i.quantity_on_hand < i.reorder_level * 1.5""",
    },
]


# ──────────────────────────────────────────────────────────────
# Realistic node trees for Lakehouse folder structure tests
# ──────────────────────────────────────────────────────────────

REALISTIC_NODE_TREE = [
    {"id": 2000, "name": "Enterprise Workspace", "type": 0, "path": "/Enterprise Workspace", "size": 0},
    {"id": 3001, "name": "Finance", "type": 0, "path": "/Enterprise Workspace/Finance", "size": 0},
    {"id": 3002, "name": "HR Policies", "type": 0, "path": "/Enterprise Workspace/HR Policies", "size": 0},
    {"id": 3003, "name": "IT Documentation", "type": 0, "path": "/Enterprise Workspace/IT Documentation", "size": 0},
    {"id": 3004, "name": "Quarterly Reports", "type": 0, "path": "/Enterprise Workspace/Finance/Quarterly Reports", "size": 0},
    {"id": 3005, "name": "Audit Trail", "type": 0, "path": "/Enterprise Workspace/Finance/Audit Trail", "size": 0},
    {"id": 54321, "name": "Q4_2024_Financial_Report.pdf", "type": 144,
     "path": "/Enterprise Workspace/Finance/Quarterly Reports/Q4_2024_Financial_Report.pdf",
     "size": 2457600, "mime_type": "application/pdf"},
    {"id": 54322, "name": "Employee_Handbook_v3.docx", "type": 144,
     "path": "/Enterprise Workspace/HR Policies/Employee_Handbook_v3.docx",
     "size": 1843200, "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    {"id": 54323, "name": "Network_Architecture_Diagram.vsdx", "type": 144,
     "path": "/Enterprise Workspace/IT Documentation/Network_Architecture_Diagram.vsdx",
     "size": 512000, "mime_type": "application/vnd.ms-visio.drawing.main+xml"},
    {"id": 54324, "name": "Budget_Template_2025.xlsx", "type": 144,
     "path": "/Enterprise Workspace/Finance/Budget_Template_2025.xlsx",
     "size": 350000, "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    {"id": 54325, "name": "SOX_Compliance_Checklist.pdf", "type": 144,
     "path": "/Enterprise Workspace/Finance/Audit Trail/SOX_Compliance_Checklist.pdf",
     "size": 890000, "mime_type": "application/pdf"},
]
