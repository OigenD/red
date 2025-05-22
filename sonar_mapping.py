apiVersion: v1
kind: ConfigMap
metadata:
  name: webhook-proxy-script
  namespace: test
data:
  webhook_proxy.py: |
    from flask import Flask, request
    import requests
    import json
    import uuid
    from datetime import datetime
    from collections import defaultdict
    import time

    app = Flask(__name__)

    CALL_SERVICE_URL = "https://10.167.40.158/emergence/api/v1/call/create"
    API_KEY = "azDEovWXQc2WyNSCsKpdR43OZE7vSRvyB6QTstn5qHK2enIGHMP0F5eRRVZBvVZH"

    # Сопоставление сервисов и контактов
    CONTACT_MAPPING = {
        "SonarQube": [{"name": "DikEV", "domainName": "DikEV"}],
        "Jenkins": [{"name": "ZenovAV", "domainName": "ZenovAV"}],
        "Postgres": [{"name": "DikEV", "domainName": "DikEV"}],
        "Unknown": []
    }

    # Резервный контакт
    FALLBACK_CONTACT = {"name": "DikEV", "domainName": "DikEV"}

    # Кэш для отслеживания обработанных алертов (fingerprint -> timestamp)
    ALERT_CACHE = defaultdict(float)
    CACHE_TTL = 300  # 5 минут

    @app.route('/webhook', methods=['POST'])
    def webhook():
        data = request.get_json()
        print("Received data:", json.dumps(data, indent=2))

        # Проверка дублирующихся алертов
        fingerprint = data["alerts"][0]["fingerprint"]
        current_time = time.time()
        if fingerprint in ALERT_CACHE and current_time - ALERT_CACHE[fingerprint] < CACHE_TTL:
            print(f"Skipping duplicate alert with fingerprint '{fingerprint}'")
            return {"message": "Duplicate alert, skipped"}, 200

        # Обновляем кэш
        ALERT_CACHE[fingerprint] = current_time

        # Генерация GUID
        guid = str(uuid.uuid4())

        # Формирование имени сервиса
        service_name = data["commonLabels"].get("service", data["commonLabels"].get("app", data["commonLabels"].get("job", "Unknown")))

        # Формирование сообщения
        status = "Active" if data["status"] == "firing" else "Resolved"
        message = f"{status}: {data['commonLabels']['alertname']} - "
        for alert in data["alerts"]:
            message += f"{alert['annotations']['summary']} - {alert['annotations']['description']}"

        # Выбор контактов
        contacts = CONTACT_MAPPING.get(service_name, CONTACT_MAPPING["Unknown"])
        if not contacts and service_name != "Unknown":
            contacts = [FALLBACK_CONTACT]
            print(f"Warning: No contacts found for service '{service_name}', using fallback contact")

        if not contacts:
            print(f"Error: No contacts available for service '{service_name}', skipping request")
            return {"error": f"No contacts for service '{service_name}'"}, 400

        payload = {
            "guid": guid,
            "serviceName": service_name,
            "message": message,
            "request": "alertmanager-webhook",
            "searchContacts": False,
            "channels": ["outbound"],
            "contacts": [
                {
                    "name": contact["name"],
                    "domainName": contact["domainName"],
                    "priority": 0
                } for contact in contacts
            ]
        }

        print("Sending payload to msk-as01apic:", json.dumps(payload, indent=2))
        print("Using API Key:", API_KEY[:10] + "...")

        headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
        try:
            response = requests.post(CALL_SERVICE_URL, json=payload, headers=headers, verify=False)
            print("Response from msk-as01apic:", response.status_code, response.text)
            if response.status_code == 500:
                print(f"Warning: Server error for service '{service_name}', response: {response.text}")
                # Очищаем кэш для этого алерта, чтобы избежать блокировки будущих попыток
                ALERT_CACHE.pop(fingerprint, None)
            return response.text, response.status_code
        except requests.RequestException as e:
            print(f"Error sending request for service '{service_name}': {e}")
            ALERT_CACHE.pop(fingerprint, None)  # Очищаем кэш при сетевой ошибке
            return {"error": str(e)}, 500

    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=5000)






receivers:
- name: call-service
  webhook_configs:
  - url: http://webhook-proxy.test.svc.cluster.local:5000/webhook
    send_resolved: true
    max_alerts: 0
    http_config:
      timeout: 10s


route:
  receiver: call-service
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 5m
