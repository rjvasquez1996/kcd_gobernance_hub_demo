{{/*
Expand the name of the chart.
*/}}
{{- define "governance-hub.name" -}}
{{- default .Chart.Name .Values.global.app | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "governance-hub.fullname" -}}
{{- if .Values.global.app }}
{{- .Values.global.app | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "governance-hub.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "governance-hub.labels" -}}
helm.sh/chart: {{ include "governance-hub.chart" . }}
{{ include "governance-hub.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "governance-hub.selectorLabels" -}}
app.kubernetes.io/name: {{ include "governance-hub.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: {{ .Values.global.app }}
{{- end }}

{{/*
Namespace
*/}}
{{- define "governance-hub.namespace" -}}
{{ .Values.global.namespace }}
{{- end }}

{{/*
App name
*/}}
{{- define "governance-hub.appName" -}}
{{ .Values.app.name }}
{{- end }}

{{/*
Nginx name
*/}}
{{- define "governance-hub.nginxName" -}}
{{ .Values.nginx.name }}
{{- end }}
