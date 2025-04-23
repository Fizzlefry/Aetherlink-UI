// <!DOCTYPE html><html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Aetherlink Code Creator</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.css" />
  <style>
    body {
      font-family: 'Segoe UI', sans-serif;
      margin: 0;
      background-color: #0e0e0e;
      color: #fff;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    header {
      background: #111;
      padding: 1rem;
      text-align: center;
      font-size: 1.5rem;
      font-weight: bold;
    }
    #language {
      margin: 1rem;
      padding: 0.5rem;
      font-size: 1rem;
      background: #1e1e1e;
      color: #fff;
      border: none;
    }
    #editor {
      flex-grow: 1;
      border-top: 1px solid #333;
    }
    .CodeMirror {
      height: 100%;
      background: #1e1e1e;
      color: #f8f8f2;
    }
    button {
      padding: 0.75rem 1.5rem;
      margin: 1rem;
      background-color: #28a745;
      color: white;
      font-size: 1rem;
      border: none;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <header>Code Creator - Powered by Aetherlink</header>
  <select id="language">
    <option value="javascript">JavaScript</option>
    <option value="htmlmixed">HTML</option>
    <option value="python">Python</option>
    <option value="xml">XML</option>
    <option value="css">CSS</option>
  </select>
  <button onclick="runCode()">Run</button>
  <div id="editor"></div>  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.js"></script>  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/javascript/javascript.min.js"></script>  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/htmlmixed/htmlmixed.min.js"></script>  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/python/python.min.js"></script>  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/xml/xml.min.js"></script>  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/css/css.min.js"></script>  <script>
    let editor = CodeMirror(document.getElementById("editor"), {
      lineNumbers: true,
      mode: "javascript",
      theme: "default",
    });

    document.getElementById("language").addEventListener("change", function () {
      editor.setOption("mode", this.value);
    });

    function runCode() {
      const lang = document.getElementById("language").value;
      const code = editor.getValue();
      if (lang === "htmlmixed") {
        const win = window.open();
        win.document.write(code);
        win.document.close();
      } else {
        alert("Execution supported only for HTML for now. Other runtimes coming soon.");
      }
    }
  </script></body>
</html>
