let nodeCount = 1;

// Constant password and username for all nodes
const CONSTANT_PASSWORD = "password";
const CONSTANT_USERNAME = "adminuser";

// Function to add a new node box
function addNodeBox(nodeData = {}) {
  const nodesContainer = document.getElementById("nodes-container");

  const nodeBox = document.createElement("div");
  nodeBox.classList.add("node-box");
  nodeBox.id = `node-box-${nodeCount}`;

  nodeBox.innerHTML = `
    <label>Node ID:</label>
    <input type="text" class="node-id" value="${nodeData.node_id || nodeCount}" required>

    <label>Management IP:</label>
    <input type="text" class="management-ip" value="${nodeData.management_ip || ''}" required>

    <div id="pci-devices-container-${nodeCount}" class="pci-devices-box">
      <h3>PCI Devices</h3>
      
      <div id="network-controller-container-${nodeCount}" class="pci-device-box">
        <label>Network Controllers:</label>
        <button type="button" id="Add_Network" class="add-controller" onclick="addNetworkController(${nodeCount})">+ Add Network Controller</button>
        <button type="button" id="Remove_Network" class="remove-controller" onclick="removeNetworkController(${nodeCount})">- Remove Network Controller</button>
      </div>
      
      <div id="storage-controller-container-${nodeCount}" class="pci-device-box">
        <label>Storage Controllers:</label>
        <button type="button" id="Add_Storage" class="add-controller" onclick="addStorageController(${nodeCount})">+ Add Storage Controller</button>
        <button type="button" id="Remove_Storage" class="remove-controller" onclick="removeStorageController(${nodeCount})">- Remove Storage Controller</button>
      </div>
    </div>
  `;

  nodesContainer.appendChild(nodeBox);
  nodeCount++;
}

// Function to add a network controller dropdown
function addNetworkController(nodeId) {
  const networkContainer = document.getElementById(`network-controller-container-${nodeId}`);
  
  const select = document.createElement('select');
  select.classList.add("network-controller");
  select.innerHTML = `
    <option value="" disabled selected>Select Network Controller</option>
    <option value="1af4:1041">Ethernet controller [0200]: Red Hat, Inc. Virtio network device [1af4:1041]</option>
  `;
  networkContainer.appendChild(select);
}

// Function to remove the last network controller dropdown
function removeNetworkController(nodeId) {
  const networkContainer = document.getElementById(`network-controller-container-${nodeId}`);
  const controllers = networkContainer.querySelectorAll(".network-controller");
  if (controllers.length > 0) {
    networkContainer.removeChild(controllers[controllers.length - 1]);
  } else {
    alert("No Network Controllers to remove.");
  }
}

// Function to add a storage controller dropdown
function addStorageController(nodeId) {
  const storageContainer = document.getElementById(`storage-controller-container-${nodeId}`);
  
  const select = document.createElement('select');
  select.classList.add("storage-controller");
  select.innerHTML = `
    <option value="" disabled selected>Select Storage Controller</option>
    <option value="1af4:1048">SCSI storage controller [0100]: Red Hat, Inc. Virtio SCSI [1af4:1048]</option>
    <option value="1af4:1042">SCSI storage controller [0100]: Red Hat, Inc. Virtio block device [1af4:1042]</option>
  `;
  storageContainer.appendChild(select);
}

// Function to remove the last storage controller dropdown
function removeStorageController(nodeId) {
  const storageContainer = document.getElementById(`storage-controller-container-${nodeId}`);
  const controllers = storageContainer.querySelectorAll(".storage-controller");
  if (controllers.length > 0) {
    storageContainer.removeChild(controllers[controllers.length - 1]);
  } else {
    alert("No Storage Controllers to remove.");
  }
}

// Add initial node box
addNodeBox();

// Add new node box on "Add Node" button click
document.getElementById("add-node").addEventListener("click", () => addNodeBox());

// Remove the last node on "Remove Node" button click
document.getElementById("remove-node").addEventListener("click", () => {
  const nodesContainer = document.getElementById("nodes-container");
  if (nodesContainer.children.length <= 1) {
    alert("At least one node is required!");
    return;
  }
  nodesContainer.removeChild(nodesContainer.lastChild);
});

// Save button click event
document.getElementById("save-button").addEventListener("click", () => {
  const nodes = [];
  const nodeBoxes = document.querySelectorAll(".node-box");

  nodeBoxes.forEach((box, index) => {
    const nodeId = box.querySelector(".node-id").value;
    const managementIp = box.querySelector(".management-ip").value;

    const networkControllers = Array.from(box.querySelectorAll(`#network-controller-container-${index + 1} select`))
      .map(select => select.value)
      .filter(value => value);

    const storageControllers = Array.from(box.querySelectorAll(`#storage-controller-container-${index + 1} select`))
      .map(select => select.value)
      .filter(value => value);

    nodes.push({
      node_id: nodeId,
      management_ip: managementIp,
      password: CONSTANT_PASSWORD,
      username: CONSTANT_USERNAME, // Add constant username
      network_controllers: networkControllers,
      storage_controllers: storageControllers
    });
  });

  const configData = {
    node_count: nodes.length,
    nodes: nodes
  };

  // Send data to backend
  fetch("/update_config", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(configData)
  })
    .then(response => response.json())
    .then(data => {
      alert("Config file updated successfully!");
    })
    .catch(error => {
      alert("Error updating config file.");
      console.error(error);
    });
});

// Execute button click event to run the Platform.py script
document.getElementById("execute-button").addEventListener("click", () => {
  fetch("/execute_platform", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    }
  })
    .then(response => response.json())
    .then(data => {
      if (data.redirect) {
        // Redirect to the output page
        window.location.href = data.redirect;
      } else if (data.error) {
        alert("Error: " + data.error);
      }
    })
    .catch(error => {
      alert("Error executing script.");
      console.error(error);
    });
});
