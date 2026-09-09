{{/*
Имя и метки. Вынесены в один файл, чтобы селектор Deployment и метки Service не
разъехались: расхождение между ними не ошибка рендеринга — под просто никогда
не попадёт за балансировщик.
*/}}
{{- define "wb-service.name" -}}
{{- required "values: `name` обязателен — без него сервис задеплоится безымянным" .Values.name -}}
{{- end -}}

{{- define "wb-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "wb-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "wb-service.labels" -}}
{{ include "wb-service.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: wb-analytics
{{- end -}}
