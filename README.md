# Automagic DevOps Pipeline / Container as a Service

## Introduction

Welcome to the Automagic DevOps Pipeline -- your all-in-one solution for effortlessly automating the software development lifecycle! Say goodbye to manual build and deployment hassles, and hello to seamless CI/CD integration, Docker-powered containerization, and comprehensive logging and monitoring.

## Description

The Automagic DevOps Pipeline is your ultimate DevOps companion, designed to simplify and streamline your development process from start to finish. Whether you're a solo developer or part of a team, this platform empowers you to automate tedious tasks, accelerate delivery, and ensure consistent, reliable deployments every time.

## Architecture

* **Highlevel Design of the System.**
* feel free to open an ISSUE mentioning any problems or ideas you might have!

  ![](arch/prod-auto.png)

## Key Features

* **GitHub Webhook Integration:** Seamlessly trigger pipeline workflows with GitHub webhook events, ensuring your CI/CD processes kick off automatically with every code push.
  
* **Continuous Integration (CI):** Effortlessly build and test your applications on every commit, ensuring code quality and reliability before deployment.
  
* **Continuous Deployment (CD):** Automatically deploy your applications to production or staging environments after successful CI runs, with minimal manual intervention.
  
* **Logging and Monitoring:** Gain insights into your pipeline executions and application performance with robust logging and monitoring solutions, enabling proactive issue detection and resolution.
  
## Get Started

1. **Clone the Repository:** Get started by cloning the Automagic DevOps Pipeline repository to your local machine.

    ```shell
    git clone https://github.com/miladhzzzz/prod-automation
    ```

2. **Run Setup Script:** Execute the Makefile or init.sh script provided in the repository to automate the setup and initialization process.

    ```shell
    cd prod-automation && chmod +x init.sh
    # This will effectively do ALL THE BELOW STEPS! plus setting up the registy configuration and cronjobs! 
    ./init.sh <YOUR_GITHUB_SECRET_HERE>
    ```

    **!!SKIP to step 6 if you use init.sh!!**

    Or just follow along this guide to set everything up manually!(also have a better picture of what needs to be done incase anything goes wrong!)

    ```shell
    # Setting up host if its freshly installed skip this if you have docker / docker-compose / git installed!!
    make setup
    ```

    Alternatively, manually execute the setup script:

    ```shell
    cd scripts
    chmod +x setup-host.sh
    ./setup-host.sh
    ```

3. **Setup Host Docker Registry:** Setup the host docker engine and /etc/hosts file to point the registry service.

    ```shell
    cd scripts && chmod +x hosts-registry.sh
    ./hosts-registry.sh insecure_registry # this will make the /etc/docker/daemon.json file and restart docker.
    ````

4. **Deploy System Components:** Deploy the entire system, including Traefik reverse proxy, Grafana, Prometheus for observability, and the production automation container.

    ```shell
    make keygen # make keygen will generate a AES 256 CBC key for keeping your secrects safe in vault!
    make up # make up will bring the project up using docker-compose
    ./scripts/hosts-registry.sh update_hosts # this will update /etc/hosts file with the registry container ip for DNS resolution.
    ```

5. **Set Github Webhook Secret:** set the github secret inside the prod-auto container with the script just like below:

    ```shell
    cd scripts && chmod +x set-env.sh
    ./set-env.sh GITHUB_WEBHOOK_SECRET <YOUR_SECRET_HERE>
    ```

6. **Kubernetes Integration:** Integrate [kube-o-matic](https://github.com/miladhzzzz/kube-o-matic) in your deployment environment to automate CD for kubernetes!

    ```shell
    make cd 
    ```

    Extract and inject your kubeconfig file to kube-o-matic:

    ```shell
    cd scripts && chmod +x extract-kubeconfig.sh
    ./extract-kubeconfig.sh -c <CONTEXT_YOU_WANT_EXTRACTED> -a <https://'prod-auto-public-ip/dns'>
    ```

7. **Utilize Docker Compose:** Use a `docker-compose.yml` in the root of your repository or a Dockerfile to build your project and define services.

    * Make sure you have either a docker-compose.yml as shown below or a Dockerfile present in the ROOT_DIR of your project!

    ```yaml
    # EXAMPLE YAML FILE FOR PROJECT AUTOMATION PIPELINE.
    version: '3.9'

    services:
        example-service:
            build:
              context: .
              dockerfile: Dockerfile

            ports: []
            # - "1111:1111"  # Adjust port if necessary
            labels: # Provide nescesary routing for traefik to pick up and automatically route to your service!
              - "traefik.enable=true"
              - "traefik.http.routers.example-service.rule=PathPrefix(`/api`)"
              - "traefik.http.middlewares.example-service.stripprefix.prefixes=/api"
              - "traefik.http.routers.example-service.middlewares=example-service@docker"
            volumes:
              - "/var/run/docker.sock:/var/run/docker.sock"
            # use environment to read secrets from your vault 
            environment:
            - DATABASE_URL: $DARABASE_URL
            networks:
            - prod-automation_prod-auto-inet

    networks:
    prod-automation_prod-auto-inet:
        external: true

    ```

8. **Set Environment Variables:** Use the API endpoint **'/vault/{project_name}'** to set environment variables for projects, ensuring smooth application execution without manual intervention.

    * Send this as a json payload to the endpoint above to set your vault secrets.

    ```json
    {
        "DATABASE_URL": "postgresql://user:password@localhost/dbname",
        "API_KEY": "abc123", 
    }
    ```

9. **Automate Build Triggers:** Trigger builds automatically when a webhook event is received, with the necessary environment variables pre-configured for seamless deployment.

   * Go to your github repository > settings > webhook and point the webhook to **'http(s)://<YOUR-DNS/PUBLIC-IP>/webhook'**.
   * Set your webhook secret.
   * Use application/json as the content type.

10. **Track Pipeline Status:** Keep track of the pipeline status in **'/status/{project_name}'** and **'/jobs'** for monitoring and reporting purposes.
  
## Experience the Magic

* **Push Code Changes:** Simply push your code changes to your GitHub repository.
  
* **Automated Workflows:** Watch as the Automagic DevOps Pipeline automates build, test, and deployment tasks seamlessly.
  
* **Monitor and Manage:** Keep tabs on your pipeline status and logs using the provided endpoints, ensuring smooth sailing throughout the development journey.

* **Version Control:** we Keep your projects updated using Git version control so you can easily revert breaking changes with a single GET request.

* **Reverse Proxy:** we also use Traefik reverse proxy you can set labels in your docker-compose to expose the services dynamically!.

* **Observability** we use Prometheus / Grafana to monitor the traefik entry point we also have a /prometheus config dir you can change it to observe all your containers or other components easily!

* ## TODO

  * [ ] Tenanat Certificate manager(Using BYOS, LetsEncrypt)
  * [ ] Client
  * [ ] Test and custom pipeline implementation
  * [ ] System state awareness
  * [x] Consitent Data management and restructuring(for Db, projects, logs directory)
  * [ ] Re-implementing the pipeline controller for scalablity(Celery)
  * [ ] Notification system
  
## Join the Journey

Ready to embark on a journey of automation and efficiency? Dive into the Automagic DevOps Pipeline, contribute your ideas, and let's make DevOps a breeze together!

## License

This project is licensed under the MIT License.


