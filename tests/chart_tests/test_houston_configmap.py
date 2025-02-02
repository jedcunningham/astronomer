import yaml
from tests.chart_tests.helm_template_generator import render_chart
import pytest
import ast


def common_test_cases(docs):
    """Test some things that should apply to all cases."""
    assert len(docs) == 1

    doc = docs[0]

    assert doc["kind"] == "ConfigMap"
    assert doc["apiVersion"] == "v1"
    assert doc["metadata"]["name"] == "release-name-houston-config"

    local_prod = yaml.safe_load(doc["data"]["local-production.yaml"])

    assert local_prod == {"nats": {"ackWait": 600000}}

    prod = yaml.safe_load(doc["data"]["production.yaml"])

    assert prod["deployments"]["helm"]["airflow"]["useAstroSecurityManager"] is True
    airflow_local_settings = prod["deployments"]["helm"]["airflow"][
        "airflowLocalSettings"
    ]

    # validate yaml-embedded python
    ast.parse(airflow_local_settings.encode())


def test_houston_configmap():
    """Validate the houston configmap and its embedded data."""
    docs = render_chart(
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )

    common_test_cases(docs)
    doc = docs[0]
    prod = yaml.safe_load(doc["data"]["production.yaml"])
    # Ensure airflow elasticsearch param is at correct location
    assert prod["deployments"]["helm"]["airflow"]["elasticsearch"]["enabled"] is True
    # Ensure elasticsearch client param is at the correct location and contains http://
    assert "node" in prod["elasticsearch"]["client"]
    assert prod["elasticsearch"]["client"]["node"].startswith("http://")
    with pytest.raises(KeyError):
        # Ensure sccEnabled is not defined by default
        assert prod["deployments"]["helm"]["sccEnabled"] is False


def test_houston_configmap_with_namespaceFreeFormEntry_true():
    """Validate the houston configmap's embedded data with
    namespaceFreeFormEntry=True."""

    docs = render_chart(
        values={"global": {"namespaceFreeFormEntry": True}},
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )
    prod = yaml.safe_load(docs[0]["data"]["production.yaml"])
    assert prod["deployments"]["namespaceFreeFormEntry"] is True


def test_houston_configmap_with_namespaceFreeFormEntry_defaults():
    """Validate the houston configmap's embedded data with
    namespaceFreeFormEntry defaults."""
    docs = render_chart(
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )
    prod = yaml.safe_load(docs[0]["data"]["production.yaml"])
    assert prod["deployments"]["namespaceFreeFormEntry"] is False


def test_houston_configmap_with_customlogging_enabled():
    """Validate the houston configmap and its embedded data with
    customLogging."""
    docs = render_chart(
        values={"global": {"customLogging": {"enabled": True}}},
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )

    common_test_cases(docs)
    doc = docs[0]
    prod = yaml.safe_load(doc["data"]["production.yaml"])

    assert "node" in prod["elasticsearch"]["client"]
    assert prod["elasticsearch"]["client"]["node"].startswith("http://") is True


def test_houston_configmapwith_scc_enabled():
    """Validate the houston configmap and its embedded data with sscEnabled."""
    docs = render_chart(
        values={"global": {"sccEnabled": True}},
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )

    common_test_cases(docs)
    doc = docs[0]
    prod = yaml.safe_load(doc["data"]["production.yaml"])

    assert prod["deployments"]["helm"]["sccEnabled"] is True


def test_houston_configmap_with_azure_enabled():
    """Validate the houston configmap and its embedded data with azure
    enabled."""
    docs = render_chart(
        values={"global": {"azure": {"enabled": True}}},
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )

    common_test_cases(docs)
    doc = docs[0]
    prod = yaml.safe_load(doc["data"]["production.yaml"])

    with pytest.raises(KeyError):
        assert prod["deployments"]["helm"]["sccEnabled"] is False

    livenessProbe = prod["deployments"]["helm"]["airflow"]["webserver"]["livenessProbe"]
    assert livenessProbe["failureThreshold"] == 25
    assert livenessProbe["periodSeconds"] == 10


def test_houston_configmap_with_config_syncer_enabled():
    """Validate the houston configmap and its embedded data with configSyncer
    enabled."""
    docs = render_chart(
        values={"astronomer": {"configSyncer": {"enabled": True}}},
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )

    common_test_cases(docs)
    doc = docs[0]
    prod = yaml.safe_load(doc["data"]["production.yaml"])
    assert prod["deployments"]["helm"]["airflow"]["webserver"]["extraVolumeMounts"] == [
        {
            "name": "signing-certificate",
            "mountPath": "/etc/airflow/tls",
            "readOnly": True,
        }
    ]
    assert prod["deployments"]["helm"]["airflow"]["webserver"]["extraVolumes"] == [
        {
            "name": "signing-certificate",
            "secret": {"secretName": "release-name-houston-jwt-signing-certificate"},
        }
    ]


def test_houston_configmap_with_config_syncer_disabled():
    """Validate the houston configmap and its embedded data with configSyncer
    disabled."""
    docs = render_chart(
        values={"astronomer": {"configSyncer": {"enabled": False}}},
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )

    common_test_cases(docs)
    doc = docs[0]
    prod_yaml = yaml.safe_load(doc["data"]["production.yaml"])
    assert (
        "extraVolumeMounts"
        not in prod_yaml["deployments"]["helm"]["airflow"]["webserver"]
    )
    assert (
        "extraVolumes" not in prod_yaml["deployments"]["helm"]["airflow"]["webserver"]
    )
    assert not prod_yaml["deployments"].get("loggingSidecar")


def test_houston_configmap_with_loggingsidecar_enabled():
    """Validate the houston configmap and its embedded data with
    loggingSidecar."""
    terminationEndpoint = "http://localhost:8000/quitquitquit"
    docs = render_chart(
        values={
            "global": {
                "loggingSidecar": {
                    "enabled": True,
                    "image": "quay.io/astronomer/ap-vector:0.22.3",
                }
            }
        },
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )

    common_test_cases(docs)
    doc = docs[0]
    prod_yaml = yaml.safe_load(doc["data"]["production.yaml"])
    log_cmd = 'log_cmd = "1> >( tee -a /var/log/sidecar-log-consumer/out.log ) 2> >( tee -a /var/log/sidecar-log-consumer/err.log >&2 )"'
    assert (
        log_cmd in prod_yaml["deployments"]["helm"]["airflow"]["airflowLocalSettings"]
    )
    assert (
        terminationEndpoint
        in prod_yaml["deployments"]["helm"]["airflow"]["airflowLocalSettings"]
    )
    assert prod_yaml["deployments"]["loggingSidecar"] == {
        "enabled": True,
        "name": "sidecar-log-consumer",
        "image": "quay.io/astronomer/ap-vector:0.22.3",
        "terminationEndpoint": "http://localhost:8000/quitquitquit",
        "customConfig": False,
    }
    assert "vector" in prod_yaml["deployments"]["loggingSidecar"]["image"]


def test_houston_configmap_with_loggingsidecar_enabled_with_overrides():
    """Validate the houston configmap and its embedded data with
    loggingSidecar."""
    sidecar_container_name = "sidecar-log-test"
    terminationEndpoint = "http://localhost:8000/quitquitquit"
    image_name = "quay.io/astronomer/ap-vector:0.22.3"
    docs = render_chart(
        values={
            "global": {
                "loggingSidecar": {
                    "enabled": True,
                    "name": sidecar_container_name,
                    "image": image_name,
                }
            }
        },
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )

    common_test_cases(docs)
    doc = docs[0]
    prod_yaml = yaml.safe_load(doc["data"]["production.yaml"])
    log_cmd = 'log_cmd = "1> >( tee -a /var/log/{sidecar_container_name}/out.log ) 2> >( tee -a /var/log/{sidecar_container_name}/err.log >&2 )"'.format(
        sidecar_container_name=sidecar_container_name
    )
    assert (
        log_cmd in prod_yaml["deployments"]["helm"]["airflow"]["airflowLocalSettings"]
    )
    assert (
        terminationEndpoint
        in prod_yaml["deployments"]["helm"]["airflow"]["airflowLocalSettings"]
    )
    assert prod_yaml["deployments"]["loggingSidecar"] == {
        "enabled": True,
        "name": sidecar_container_name,
        "image": "quay.io/astronomer/ap-vector:0.22.3",
        "terminationEndpoint": terminationEndpoint,
        "customConfig": False,
    }
    assert "vector" in prod_yaml["deployments"]["loggingSidecar"]["image"]


def test_houston_configmap_with_loggingsidecar_customConfig_enabled():
    """Validate the houston configmap and its embedded data with loggingSidecar
    customConfig Enabled."""
    sidecar_container_name = "sidecar-log-test"
    terminationEndpoint = "http://localhost:8000/quitquitquit"
    image_name = "quay.io/astronomer/ap-vector:0.22.3"
    docs = render_chart(
        values={
            "global": {
                "loggingSidecar": {
                    "enabled": True,
                    "name": sidecar_container_name,
                    "customConfig": True,
                    "image": image_name,
                }
            }
        },
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )

    common_test_cases(docs)
    doc = docs[0]
    prod_yaml = yaml.safe_load(doc["data"]["production.yaml"])
    log_cmd = 'log_cmd = "1> >( tee -a /var/log/{sidecar_container_name}/out.log ) 2> >( tee -a /var/log/{sidecar_container_name}/err.log >&2 )"'.format(
        sidecar_container_name=sidecar_container_name
    )
    assert (
        log_cmd in prod_yaml["deployments"]["helm"]["airflow"]["airflowLocalSettings"]
    )
    assert (
        terminationEndpoint
        in prod_yaml["deployments"]["helm"]["airflow"]["airflowLocalSettings"]
    )
    assert prod_yaml["deployments"]["loggingSidecar"] == {
        "enabled": True,
        "name": sidecar_container_name,
        "image": "quay.io/astronomer/ap-vector:0.22.3",
        "terminationEndpoint": terminationEndpoint,
        "customConfig": True,
    }
    assert "vector" in prod_yaml["deployments"]["loggingSidecar"]["image"]


def test_houston_configmap_with_loggingsidecar_enabled_with_custom_env_overrides():
    """Validate the houston configmap and its embedded data with
    loggingSidecar."""
    sidecar_container_name = "sidecar-log-test"
    terminationEndpoint = "http://localhost:8000/quitquitquit"
    image_name = "quay.io/astronomer/ap-vector:0.22.3"
    docs = render_chart(
        values={
            "global": {
                "loggingSidecar": {
                    "enabled": True,
                    "name": sidecar_container_name,
                    "image": image_name,
                    "extraEnv": [
                        {
                            "name": "ES_USER",
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": "elastic-creds",
                                    "key": "ESUSER",
                                }
                            },
                        },
                        {
                            "name": "ES_PASS",
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": "elastic-creds",
                                    "key": "ESPASS",
                                }
                            },
                        },
                    ],
                }
            }
        },
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )
    common_test_cases(docs)
    doc = docs[0]
    prod_yaml = yaml.safe_load(doc["data"]["production.yaml"])
    print(prod_yaml)
    log_cmd = 'log_cmd = "1> >( tee -a /var/log/{sidecar_container_name}/out.log ) 2> >( tee -a /var/log/{sidecar_container_name}/err.log >&2 )"'.format(
        sidecar_container_name=sidecar_container_name
    )
    assert (
        log_cmd in prod_yaml["deployments"]["helm"]["airflow"]["airflowLocalSettings"]
    )
    assert (
        terminationEndpoint
        in prod_yaml["deployments"]["helm"]["airflow"]["airflowLocalSettings"]
    )
    assert prod_yaml["deployments"]["loggingSidecar"] == {
        "enabled": True,
        "name": sidecar_container_name,
        "image": "quay.io/astronomer/ap-vector:0.22.3",
        "terminationEndpoint": terminationEndpoint,
        "customConfig": False,
        "extraEnv": [
            {
                "name": "ES_USER",
                "valueFrom": {
                    "secretKeyRef": {"name": "elastic-creds", "key": "ESUSER"}
                },
            },
            {
                "name": "ES_PASS",
                "valueFrom": {
                    "secretKeyRef": {"name": "elastic-creds", "key": "ESPASS"}
                },
            },
        ],
    }

    assert "vector" in prod_yaml["deployments"]["loggingSidecar"]["image"]


def test_houston_configmap_with_loggingsidecar_enabled_with_resource_overrides():
    """Validate the houston configmap and its embedded data with
    loggingSidecar."""
    sidecar_container_name = "sidecar-log-test"
    terminationEndpoint = "http://localhost:8000/quitquitquit"
    image_name = "quay.io/astronomer/ap-vector:0.22.3"
    docs = render_chart(
        values={
            "global": {
                "loggingSidecar": {
                    "enabled": True,
                    "name": sidecar_container_name,
                    "image": image_name,
                    "resources": {
                        "requests": {"memory": "386Mi", "cpu": "100m"},
                        "limits": {"memory": "386Mi", "cpu": "100m"},
                    },
                }
            }
        },
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )
    common_test_cases(docs)
    doc = docs[0]
    prod_yaml = yaml.safe_load(doc["data"]["production.yaml"])
    log_cmd = 'log_cmd = "1> >( tee -a /var/log/{sidecar_container_name}/out.log ) 2> >( tee -a /var/log/{sidecar_container_name}/err.log >&2 )"'.format(
        sidecar_container_name=sidecar_container_name
    )
    assert (
        log_cmd in prod_yaml["deployments"]["helm"]["airflow"]["airflowLocalSettings"]
    )
    assert (
        terminationEndpoint
        in prod_yaml["deployments"]["helm"]["airflow"]["airflowLocalSettings"]
    )
    assert prod_yaml["deployments"]["loggingSidecar"] == {
        "enabled": True,
        "name": sidecar_container_name,
        "image": "quay.io/astronomer/ap-vector:0.22.3",
        "terminationEndpoint": terminationEndpoint,
        "customConfig": False,
        "resources": {
            "requests": {"memory": "386Mi", "cpu": "100m"},
            "limits": {"memory": "386Mi", "cpu": "100m"},
        },
    }

    assert "vector" in prod_yaml["deployments"]["loggingSidecar"]["image"]


cron_test_data = [
    ("development-angular-system-6091", 3),
    ("development-arithmetic-phases-5695", 3),
    ("development-empty-aurora-8527", 3),
    ("development-explosive-inclination-4552", 3),
    ("development-infrared-nadir-2873", 3),
    ("development-barren-telemetry-6087", 4),
    ("development-geocentric-cluster-5666", 4),
    ("development-mathematical-supernova-1523", 4),
    ("development-cometary-terrestrial-2880", 5),
    ("development-nuclear-gegenschein-1657", 5),
    ("development-quasarian-telescope-4189", 5),
    ("development-traditional-universe-0643", 5),
    ("development-asteroidal-space-6369", 6),
    ("development-blazing-horizon-1542", 6),
    ("development-boreal-inclination-4658", 6),
    ("development-exact-ionosphere-3963", 6),
    ("development-extrasolar-meteor-4188", 6),
    ("development-inhabited-dust-4345", 6),
    ("development-nebular-singularity-6518", 6),
    ("development-arithmetic-sky-0424", 7),
    ("development-true-century-8320", 7),
    ("development-angular-radian-2199", 8),
    ("development-scientific-cosmonaut-1863", 8),
    ("development-uninhabited-wavelength-9355", 8),
    ("development-false-spacecraft-1944", 9),
    ("development-mathematical-equator-2284", 9),
    ("development-amateur-horizon-3115", 12),
    ("development-devoid-terminator-0587", 12),
    ("development-optical-asteroid-4621", 12),
]


@pytest.mark.parametrize(
    "test_data", cron_test_data, ids=[x[0] for x in cron_test_data]
)
def test_cron_splay(test_data):
    """Test that our adler32sum method of generating deterministic random
    numbers works."""
    doc = render_chart(
        name=test_data[0],
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )[0]

    production_yaml = yaml.safe_load(doc["data"]["production.yaml"])
    cron_schedule = production_yaml["deployments"]["helm"]["airflow"]["cleanup"][
        "schedule"
    ]
    cron_minute = cron_schedule.split("-")[0]
    # We are comparing after the addition of 3, which happens in the configmap template
    assert (
        str(test_data[1]) == cron_minute
    ), f'test_data should be: ("{test_data[0]}", {cron_minute}),'


def test_houston_configmapwith_update_airflow_runtime_checks_enabled():
    """Validate the houston configmap and its embedded data with
    updateAirflowCheck and updateRuntimeCheck."""
    docs = render_chart(
        values={
            "astronomer": {
                "houston": {
                    "updateAirflowCheck": {"enabled": True},
                    "updateRuntimeCheck": {"enabled": True},
                }
            }
        },
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )
    common_test_cases(docs)
    doc = docs[0]

    prod = yaml.safe_load(doc["data"]["production.yaml"])

    assert prod["updateAirflowCheckEnabled"] is True
    assert prod["updateRuntimeCheckEnabled"] is True


def test_houston_configmapwith_update_airflow_runtime_checks_disabled():
    """Validate the houston configmap and its embedded data with
    updateAirflowCheck and updateRuntimeCheck."""
    docs = render_chart(
        values={
            "astronomer": {
                "houston": {
                    "updateAirflowCheck": {"enabled": False},
                    "updateRuntimeCheck": {"enabled": False},
                }
            }
        },
        show_only=["charts/astronomer/templates/houston/houston-configmap.yaml"],
    )
    common_test_cases(docs)
    doc = docs[0]

    prod = yaml.safe_load(doc["data"]["production.yaml"])
    assert prod["updateAirflowCheckEnabled"] is False
    assert prod["updateRuntimeCheckEnabled"] is False
