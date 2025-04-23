<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Ask Aether</title>
  <style>
    body {
      font-family: 'Segoe UI', sans-serif;
      background-color: #0e0e0e;
      color: #fff;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      padding: 1rem;
    }
    h1 {
      font-size: 2rem;
      margin-bottom: 1rem;
    }
    textarea {
      width: 80%;
      height: 150px;
      margin-bottom: 1rem;
      background-color: #1e1e1e;
      color: #fff;
      border: 1px solid #333;
      padding: 1rem;
      font-size: 1rem;
    }
    button {
      padding: 0.5rem 1.5rem;
      font-size: 1rem;
      background-color: #28a745;
      color: white;
      border: none;
      cursor: pointer;
    }
    #response {
      margin-top: 2rem;
      width: 80%;
      background-color: #111;
      padding: 1rem;
      border-radius: 5px;
      border: 1px solid #333;
    }
  </style>
</head>
<body>
  <h1>Ask Aether</h1>
  <textarea id="userInput" placeholder="Type your question or command here..."></textarea>
  <button onclick="askAether()">Ask</button>
  <div id="response">Awaiting divine instruction...</div>

  <script>
    function askAether() {
      const input = document.getElementById('userInput').value;
      const responseEl = document.getElementById('response');
      
      // Simulate Aether's response (replace with real AI connection in future phases)
      setTimeout(() => {
        responseEl.innerText = `"${input}" received. Aether is thinking...`;
      }, 1000);
    }
  </script>
</body>
</html>// AI terminal interface for live suggestions, templates, and help
