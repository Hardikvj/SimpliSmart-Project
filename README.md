# SimpliSmart-Project
1. Install dependencies like Python & minikube cluster using choco.
2. Install python packages [py -m pip install pyyaml]
3. Start the minikube cluster using DockerDesktop [minikube start --driver=docker]
4. Check the status of the cluster. [minikube status]
   ![Capture](https://github.com/user-attachments/assets/3b9f92a7-263e-4a9d-8c56-60ad21dfb2c0)
5. Run the python script to connect to the cluster [ py .\simplismart-kube.py connect ]
   ![Capture1](https://github.com/user-attachments/assets/78426f4c-a905-472f-a7c1-7adaa6ac2c14)
6. Install the helm & Keda depencdency using the python script [ py .\simplismart-kube.py install --helm --keda ]
   ![Capture-2](https://github.com/user-attachments/assets/0cea4e01-639a-45f7-a8e6-2744b79be3cf)
7.  Deploy the "simplismart-app" using the python script [ py .\simplismart-kube.py deploy simplismart-app nginx --keda-config keda-config.json ]
    ![Capture3](https://github.com/user-attachments/assets/554d5a8a-7937-4b00-b4c4-2c6061ca6c3b)
8.  Check for the running pods [ kubectl get pods ]
9.  Check for deployments on keda namespace [ kubectl get deployments -n keda ]
    ![Capture4](https://github.com/user-attachments/assets/8a4cf221-353e-4212-aa79-00fa60592b77)
10. Check for API resources [ kubectl api-resources | findstr keda ]
    ![Capture5](https://github.com/user-attachments/assets/342c8b37-dc34-42eb-91c6-5d399a576170)
