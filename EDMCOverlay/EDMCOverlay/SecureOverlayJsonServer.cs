using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;
using System.Text.RegularExpressions;

namespace EDMCOverlay
{
    /// <summary>
    /// Enhanced JSON server with security features and rate limiting
    /// </summary>
    public class SecureOverlayJsonServer
    {
        private readonly OverlayRenderer _renderer;
        public const int DefaultTtl = 5;
        public const int MaxClients = 5;
        public const int MaxMessageSize = 10240; // 10KB
        public const int RateLimitPerSecond = 100; // Max 100 messages per second per client

        private readonly ConcurrentDictionary<string, ClientInfo> _clients = new();
        private readonly ConcurrentDictionary<string, InternalGraphic> _graphics = new();
        private readonly Timer _cleanupTimer;
        private readonly object _statsLock = new object();

        private volatile int _messageCount = 0;
        private volatile int _messageUnknownCount = 0;
        private volatile int _messageErrorCount = 0;
        private volatile int _messageRateLimitedCount = 0;

        public int MessageCount => _messageCount;
        public int MessageUnknownCount => _messageUnknownCount;
        public int MessageErrorCount => _messageErrorCount;
        public int MessageRateLimitedCount => _messageRateLimitedCount;

        public Logger Logger = Logger.GetInstance(typeof(SecureOverlayJsonServer));

        public int Port { get; private set; }

        private readonly TcpListener _listener;
        private readonly CancellationTokenSource _cancellationTokenSource = new();
        private readonly List<Task> _clientTasks = new();

        private readonly HashSet<string> _allowedCommands = new()
        {
            "exit", "clear", "status"
        };

        private readonly Regex _colorPattern = new(@"^(#[0-9A-Fa-f]{6}|red|green|blue|yellow|white|black)$", 
            RegexOptions.Compiled);

        public Dictionary<string, InternalGraphic> Graphics => new(_graphics);

        /// <summary>
        /// Client information for rate limiting and tracking
        /// </summary>
        private class ClientInfo
        {
            public string ClientId { get; set; } = Guid.NewGuid().ToString();
            public DateTime LastMessageTime { get; set; } = DateTime.UtcNow;
            public Queue<DateTime> MessageTimes { get; set; } = new Queue<DateTime>();
            public int TotalMessages { get; set; } = 0;
            public string RemoteEndPoint { get; set; } = string.Empty;
        }

        public SecureOverlayJsonServer(int port, OverlayRenderer renderer)
        {
            Port = port;
            _renderer = renderer;
            _listener = new TcpListener(IPAddress.Loopback, Port);
            
            // Cleanup timer runs every 30 seconds
            _cleanupTimer = new Timer(CleanupExpiredGraphics, null, TimeSpan.FromSeconds(30), TimeSpan.FromSeconds(30));
            
            Logger.Info($"Secure overlay server initialized on port {Port}");
        }

        public void Start()
        {
            try
            {
                _listener.Start();
                Logger.Info($"Server listening on {IPAddress.Loopback}:{Port}");

                // Accept connections asynchronously
                _ = Task.Run(AcceptClientsAsync, _cancellationTokenSource.Token);
            }
            catch (Exception ex)
            {
                Logger.Error($"Failed to start server: {ex.Message}");
                throw;
            }
        }

        public void Stop()
        {
            try
            {
                _cancellationTokenSource.Cancel();
                _listener?.Stop();
                _cleanupTimer?.Dispose();

                // Wait for client tasks to complete
                Task.WaitAll(_clientTasks.ToArray(), TimeSpan.FromSeconds(5));
                
                Logger.Info("Server stopped successfully");
            }
            catch (Exception ex)
            {
                Logger.Error($"Error stopping server: {ex.Message}");
            }
        }

        private async Task AcceptClientsAsync()
        {
            while (!_cancellationTokenSource.Token.IsCancellationRequested)
            {
                try
                {
                    var tcpClient = await _listener.AcceptTcpClientAsync();
                    var clientEndpoint = tcpClient.Client.RemoteEndPoint?.ToString() ?? "unknown";
                    
                    if (_clients.Count >= MaxClients)
                    {
                        Logger.Warn($"Max clients reached, rejecting connection from {clientEndpoint}");
                        tcpClient.Close();
                        continue;
                    }

                    var clientInfo = new ClientInfo
                    {
                        RemoteEndPoint = clientEndpoint
                    };
                    
                    _clients.TryAdd(clientInfo.ClientId, clientInfo);
                    
                    var clientTask = Task.Run(() => HandleClientAsync(tcpClient, clientInfo), 
                        _cancellationTokenSource.Token);
                    _clientTasks.Add(clientTask);
                    
                    Logger.Info($"Client connected: {clientEndpoint} (ID: {clientInfo.ClientId})");
                }
                catch (ObjectDisposedException)
                {
                    // Server is shutting down
                    break;
                }
                catch (Exception ex)
                {
                    Logger.Error($"Error accepting client connection: {ex.Message}");
                }
            }
        }

        private async Task HandleClientAsync(TcpClient client, ClientInfo clientInfo)
        {
            NetworkStream stream = null;
            StreamReader reader = null;

            try
            {
                client.ReceiveTimeout = 30000; // 30 second timeout
                stream = client.GetStream();
                reader = new StreamReader(stream, Encoding.UTF8);

                while (!_cancellationTokenSource.Token.IsCancellationRequested && client.Connected)
                {
                    var line = await reader.ReadLineAsync();
                    if (string.IsNullOrEmpty(line))
                        break;

                    await ProcessMessageAsync(line, clientInfo);
                }
            }
            catch (Exception ex)
            {
                Logger.Error($"Error handling client {clientInfo.ClientId}: {ex.Message}");
            }
            finally
            {
                // Cleanup
                reader?.Dispose();
                stream?.Dispose();
                client?.Close();
                _clients.TryRemove(clientInfo.ClientId, out _);
                
                Logger.Info($"Client disconnected: {clientInfo.RemoteEndPoint} (ID: {clientInfo.ClientId})");
            }
        }

        private async Task ProcessMessageAsync(string jsonMessage, ClientInfo clientInfo)
        {
            try
            {
                // Rate limiting check
                if (!CheckRateLimit(clientInfo))
                {
                    Interlocked.Increment(ref _messageRateLimitedCount);
                    Logger.Warn($"Rate limit exceeded for client {clientInfo.ClientId}");
                    return;
                }

                // Size validation
                if (jsonMessage.Length > MaxMessageSize)
                {
                    Interlocked.Increment(ref _messageErrorCount);
                    Logger.Warn($"Message too large from client {clientInfo.ClientId}: {jsonMessage.Length} bytes");
                    return;
                }

                // Parse and validate JSON
                var messageObj = JsonConvert.DeserializeObject<Dictionary<string, object>>(jsonMessage);
                if (messageObj == null)
                {
                    Interlocked.Increment(ref _messageErrorCount);
                    Logger.Warn($"Invalid JSON from client {clientInfo.ClientId}");
                    return;
                }

                // Security validation
                if (!ValidateMessage(messageObj, clientInfo))
                {
                    Interlocked.Increment(ref _messageErrorCount);
                    return;
                }

                // Process the message
                await ProcessValidatedMessageAsync(messageObj, clientInfo);
                
                Interlocked.Increment(ref _messageCount);
                clientInfo.TotalMessages++;
            }
            catch (JsonException ex)
            {
                Interlocked.Increment(ref _messageErrorCount);
                Logger.Error($"JSON parsing error from client {clientInfo.ClientId}: {ex.Message}");
            }
            catch (Exception ex)
            {
                Interlocked.Increment(ref _messageErrorCount);
                Logger.Error($"Error processing message from client {clientInfo.ClientId}: {ex.Message}");
            }
        }

        private bool CheckRateLimit(ClientInfo clientInfo)
        {
            var now = DateTime.UtcNow;
            clientInfo.LastMessageTime = now;
            
            // Clean old message times (older than 1 second)
            while (clientInfo.MessageTimes.Count > 0 && 
                   (now - clientInfo.MessageTimes.Peek()).TotalSeconds > 1)
            {
                clientInfo.MessageTimes.Dequeue();
            }
            
            if (clientInfo.MessageTimes.Count >= RateLimitPerSecond)
            {
                return false;
            }
            
            clientInfo.MessageTimes.Enqueue(now);
            return true;
        }

        private bool ValidateMessage(Dictionary<string, object> message, ClientInfo clientInfo)
        {
            try
            {
                // Check for required fields
                if (!message.ContainsKey("id"))
                {
                    Logger.Warn($"Message missing 'id' field from client {clientInfo.ClientId}");
                    return false;
                }

                // Validate string lengths
                if (message.TryGetValue("text", out var textObj) && textObj is string text)
                {
                    if (text.Length > 1000)
                    {
                        Logger.Warn($"Text too long from client {clientInfo.ClientId}: {text.Length} chars");
                        return false;
                    }
                }

                // Validate color format
                if (message.TryGetValue("color", out var colorObj) && colorObj is string color)
                {
                    if (!_colorPattern.IsMatch(color))
                    {
                        Logger.Warn($"Invalid color format from client {clientInfo.ClientId}: {color}");
                        return false;
                    }
                }

                // Validate commands
                if (message.TryGetValue("command", out var commandObj) && commandObj is string command)
                {
                    if (!_allowedCommands.Contains(command.ToLowerInvariant()))
                    {
                        Logger.Warn($"Unauthorized command from client {clientInfo.ClientId}: {command}");
                        return false;
                    }
                }

                // Validate numeric ranges
                foreach (var field in new[] { "x", "y", "w", "h" })
                {
                    if (message.TryGetValue(field, out var valueObj))
                    {
                        if (double.TryParse(valueObj.ToString(), out var value))
                        {
                            if (value < -10000 || value > 10000)
                            {
                                Logger.Warn($"Numeric value out of range from client {clientInfo.ClientId}: {field}={value}");
                                return false;
                            }
                        }
                    }
                }

                return true;
            }
            catch (Exception ex)
            {
                Logger.Error($"Error validating message from client {clientInfo.ClientId}: {ex.Message}");
                return false;
            }
        }

        private async Task ProcessValidatedMessageAsync(Dictionary<string, object> message, ClientInfo clientInfo)
        {
            try
            {
                // Handle special commands
                if (message.TryGetValue("command", out var commandObj) && commandObj is string command)
                {
                    await HandleCommandAsync(command, clientInfo);
                    return;
                }

                // Create graphic from message
                var graphic = CreateGraphicFromMessage(message, clientInfo.ClientId);
                if (graphic != null)
                {
                    _graphics.AddOrUpdate(graphic.Id, graphic, (key, oldValue) => graphic);
                    Logger.Debug($"Updated graphic '{graphic.Id}' from client {clientInfo.ClientId}");
                }
            }
            catch (Exception ex)
            {
                Logger.Error($"Error processing validated message from client {clientInfo.ClientId}: {ex.Message}");
            }
        }

        private async Task HandleCommandAsync(string command, ClientInfo clientInfo)
        {
            switch (command.ToLowerInvariant())
            {
                case "exit":
                    Logger.Info($"Exit command received from client {clientInfo.ClientId}");
                    _cancellationTokenSource.Cancel();
                    break;
                    
                case "clear":
                    _graphics.Clear();
                    Logger.Info($"Clear command executed by client {clientInfo.ClientId}");
                    break;
                    
                case "status":
                    Logger.Info($"Status requested by client {clientInfo.ClientId}: " +
                              $"Messages: {MessageCount}, Errors: {MessageErrorCount}, " +
                              $"Graphics: {_graphics.Count}, Clients: {_clients.Count}");
                    break;
            }
        }

        private InternalGraphic CreateGraphicFromMessage(Dictionary<string, object> message, string clientId)
        {
            try
            {
                var graphic = new InternalGraphic
                {
                    Id = message["id"].ToString(),
                    ClientId = clientId,
                    TTL = message.TryGetValue("ttl", out var ttlObj) && 
                          int.TryParse(ttlObj.ToString(), out var ttl) ? ttl : DefaultTtl,
                    // Add other properties as needed
                };

                return graphic;
            }
            catch (Exception ex)
            {
                Logger.Error($"Error creating graphic from message: {ex.Message}");
                return null;
            }
        }

        private void CleanupExpiredGraphics(object state)
        {
            try
            {
                var now = DateTime.UtcNow;
                var expiredKeys = _graphics
                    .Where(kvp => kvp.Value.IsExpired(now))
                    .Select(kvp => kvp.Key)
                    .ToList();

                foreach (var key in expiredKeys)
                {
                    _graphics.TryRemove(key, out _);
                }

                if (expiredKeys.Count > 0)
                {
                    Logger.Debug($"Cleaned up {expiredKeys.Count} expired graphics");
                }
            }
            catch (Exception ex)
            {
                Logger.Error($"Error during cleanup: {ex.Message}");
            }
        }

        public void Dispose()
        {
            Stop();
            _cancellationTokenSource?.Dispose();
            _cleanupTimer?.Dispose();
        }
    }
}