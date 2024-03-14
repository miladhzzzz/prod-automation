import yaml
from jinja2 import Template


class ManifestGen():

    deployment_template_file = "manifests/deployment_template.yml"  # Path to your deployment template file
    service_template_file = "manifests/service_template.yml"  # Path to your service template file

    def load_template(template_file):
        with open(template_file, 'r') as f:
            return yaml.safe_load(f)

    def generate_kubernetes_manifests(self, compose_file):
        deployment_template = self.load_template(self.deployment_template_file)
        service_template = self.load_template(self.service_template_file)

        with open(compose_file, 'r') as f:
            docker_compose = yaml.safe_load(f)

        for service_name, service_config in docker_compose['services'].items():
            # Render Deployment YAML
            deployment_yaml = Template(yaml.dump(deployment_template)).render(service_name=service_name, **service_config)

            # Render Service YAML
            service_yaml = Template(yaml.dump(service_template)).render(service_name=service_name, **service_config)

            # Write to files
            with open(f'{service_name}_deployment.yml', 'w') as deployment_file:
                deployment_file.write(deployment_yaml)
            with open(f'{service_name}_service.yml', 'w') as service_file:
                service_file.write(service_yaml)