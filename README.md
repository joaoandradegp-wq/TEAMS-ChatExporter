 <h1 align="center">💬 Teams Chat Exporter</h1>

<p align="center">
  O Teams Chat Exporter é um aplicativo desktop que facilita a exportação do histórico de conversas do Microsoft Teams para arquivos de texto organizados.
  Selecione um período, colete mensagens com autores e datas, e salve as conversas para consulta futura por meio de uma interface gráfica simples.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow">
  <img src="https://img.shields.io/badge/Plataforma-Windows-blue?logo=windows">
  <img src="https://img.shields.io/badge/Fonte-Microsoft%20Teams-6264A7?logo=microsoftteams">
  <img src="https://img.shields.io/badge/Idioma-PT--BR-purple">
  <img src="https://img.shields.io/badge/Interface-Tkinter-green">
</p>

---

## ✨ Funcionalidades

<table>

<tr>
<td width="50%" valign="top">

<h3>💬 Exportação de Conversas</h3>

<ul>
<li>Exporta conversas do Microsoft Teams para arquivos TXT</li>
<li>Inclui conteúdo das mensagens, autores, datas e horários</li>
<li>Identifica nomes de anexos presentes nas conversas</li>
<li>Organiza as mensagens em ordem cronológica</li>
<li>Inclui informações sobre a exportação e a quantidade de mensagens</li>
</ul><br>

</td>
<td width="50%" valign="top">

<h3>📅 Seleção de Período</h3>

<ul>
<li>Define datas de início e término</li>
<li>Permite exportar todo o histórico disponível</li>
<li>Atalhos para hoje, últimos 7, 30 ou 90 dias</li>
<li>Opção para exportar o mês atual</li>
<li>Filtra as mensagens conforme o período selecionado</li>
</ul><br>

</td>
</tr>

<tr>
<td width="50%" valign="top">

<h3>🌐 Conexão com o Navegador</h3>

<ul>
<li>Abre o navegador diretamente pelo aplicativo</li>
<li>Permite acessar o Microsoft Teams com sua conta</li>
<li>Conecta-se à sessão do navegador</li>
<li>Salva as configurações do navegador entre execuções</li>
<li>Permite testar a conexão antes da exportação</li>
</ul><br>

</td>
<td width="50%" valign="top">

<h3>⚙️ Controle da Exportação</h3>

<ul>
<li>Define o local de salvamento do arquivo</li>
<li>Configura o intervalo entre as etapas de coleta</li>
<li>Acompanha o progresso em tempo real</li>
<li>Permite interromper uma exportação</li>
<li>Abre o arquivo gerado ou sua pasta de destino</li>
</ul><br>

</td>
</tr>

<tr>
<td width="50%" valign="top">

<h3>📄 Arquivo de Texto</h3>

<ul>
<li>Gera arquivos TXT de fácil leitura</li>
<li>Registra o título da conversa e a data da exportação</li>
<li>Informa o período selecionado</li>
<li>Apresenta a quantidade e os registros das mensagens</li>
<li>Permite consultar o conteúdo em editores de texto comuns</li>
</ul><br>

</td>
<td width="50%" valign="top">

<h3>🔍 Diagnóstico</h3>

<ul>
<li>Exibe registros da execução e informações de progresso</li>
<li>Apresenta erros de conexão ou extração</li>
<li>Gera um arquivo HTML de diagnóstico quando nenhum texto de mensagem é extraído</li>
<li>Permite ajustar a velocidade de coleta para conversas extensas</li>
</ul><br>

</td>
</tr>

</table>

---

## 🚀 Como utilizar

<ol>
<li><b>Abra o aplicativo.</b> Execute o Teams Chat Exporter.</li>
<li><b>Conecte o navegador.</b> Clique em <code>Open Browser</code> e entre no Microsoft Teams.</li>
<li><b>Selecione a conversa.</b> Abra o chat que deseja exportar.</li>
<li><b>Escolha o período.</b> Defina as datas de início e término ou selecione a opção para exportar desde o início.</li>
<li><b>Configure o destino.</b> Escolha onde salvar o arquivo TXT, se necessário.</li>
<li><b>Inicie a exportação.</b> Clique em <code>Execute</code> e acompanhe o registro de progresso.</li>
<li><b>Consulte o resultado.</b> Abra o arquivo gerado diretamente pelo aplicativo.</li>
</ol>

---

## 📄 Exemplo de exportação

O arquivo exportado segue uma estrutura simples e legível:

```text
Conversa: Discussão do Projeto
Exportado em: 16/10/2026 15:00
Período: 01/10/2026 a 16/10/2026
Total de mensagens: 125
============================================================

[01/10/2026 09:15] Usuário A: Bom dia, pessoal!

[01/10/2026 09:18] Usuário B: A reunião está confirmada.

[01/10/2026 09:20] Usuário A: [Anexos: project_plan.xlsx]
```

*Exemplo ilustrativo. O conteúdo real depende das mensagens encontradas na conversa.*

---

## 📁 Arquivos gerados

| Arquivo | Descrição |
|---|---|
| `teams_<chat>_<timestamp>.txt` | Conversa exportada |
| `teams_export.ini` | Configurações salvas do navegador e da conexão |
| `teams_debug.html` | Arquivo de diagnóstico gerado quando nenhum texto de mensagem é extraído |

Por padrão, o arquivo exportado é salvo no diretório do aplicativo. É possível selecionar outro destino antes de iniciar a exportação.

---

## 🛠️ Tecnologias utilizadas

<ul>
<li>Python</li>
<li>Tkinter</li>
<li>Playwright</li>
<li>Microsoft Teams Web</li>
<li>Chrome DevTools Protocol (CDP)</li>
<li>HTML</li>
<li>Arquivos de configuração INI</li>
<li>Manipulação e extração de dados do DOM</li>
</ul>

---

## 🎯 Casos de uso

<ul>
<li>Manter uma cópia local de conversas de trabalho</li>
<li>Organizar discussões de projetos</li>
<li>Consultar mensagens antigas</li>
<li>Registrar decisões e comunicações importantes</li>
<li>Pesquisar conversas exportadas usando um editor de texto</li>
</ul>

---

## ⚠️ Observações

<ul>
<li>Desenvolvido para ambientes desktop Windows.</li>
<li>Requer acesso ao Microsoft Teams e uma sessão autenticada no navegador.</li>
<li>A conexão depende da disponibilidade do endereço de depuração configurado.</li>
<li>O tempo de exportação varia conforme o tamanho do histórico da conversa.</li>
<li>Os nomes dos anexos podem ser registrados, mas os arquivos não são baixados.</li>
<li>Alterações na interface do Microsoft Teams podem afetar o processo de exportação.</li>
<li>As conversas exportadas podem conter informações confidenciais. Armazene e compartilhe os arquivos conforme as políticas da sua organização.</li>
</ul>

---

## 🔒 Privacidade e segurança

O Teams Chat Exporter coleta mensagens das conversas disponíveis na sessão do Teams aberta no navegador conectado.

Utilize o aplicativo somente em conversas às quais você tenha autorização de acesso. Proteja os arquivos exportados e siga as políticas aplicáveis de segurança, tratamento e retenção de dados.

---

## 📸 Preview

<p align="center">
  <img width="500" alt="image" src="https://github.com/user-attachments/assets/e09956a9-e86d-4ccd-ac14-d343c54f2683" />
</p>

---

<p align="center">
  Desenvolvido para facilitar a preservação e a consulta de conversas do Microsoft Teams. 💬
</p>
