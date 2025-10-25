using System.Collections.Concurrent;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace EDMCOverlay;

/// <summary>
/// Enhanced JSON server with security features, rate limiting, and .NET 8.0 optimizations
/// </summary>
public sealed partial class SecureOverlayJsonServer : BackgroundService, IDisposable
{
    private readonly OverlayRenderer _renderer;
    private readonly ILogger<SecureOverlayJsonServer> _logger;
    private readonly IConfiguration _configuration;
    
    // Configuration values
    private readonly int _maxClients;
    private readonly int _maxMessageSize;
    private readonly int _rateLimitPerSecond;
    private readonly IPAddress _bindAddress;
    private readonly int _port;
    
    // State management
    private readonly ConcurrentDictionary<string, ClientInfo> _clients = new();
    private readonly ConcurrentDictionary<string, InternalGraphic> _graphics = new();
    private readonly PeriodicTimer _cleanupTimer;
    
    // Performance counters (thread-safe)
    private long _messageCount;
    private long _messageUnknownCount;
    private long _messageErrorCount;
    private long _messageRateLimitedCount;
    
    // Network components
    private TcpListener? _listener;
    private readonly List<Task> _clientTasks = [];
    
    // Security patterns (compiled regex for performance)
    [GeneratedRegex(@"^(#[0-9A-Fa-f]{6}|red|green|blue|yellow|white|black)$", RegexOptions.Compiled)]
    private static partial Regex ColorPattern();
    
    [GeneratedRegex(@"^[a-zA-Z0-9_-]{1,50}$", RegexOptions.Compiled)]
    private static partial Regex IdPattern();

    // Read-only collections for security
    private readonly HashSet<string> _allowedCommands;

    // Performance metrics
    public long MessageCount => Interlocked.Read(ref _messageCount);
    public long MessageUnknownCount => Interlocked.Read(ref _messageUnknownCount);
    public long MessageErrorCount => Interlocked.Read(ref _messageErrorCount);
    public long MessageRateLimitedCount => Interlocked.Read(ref _messageRateLimitedCount);
    public int ActiveClients => _clients.Count;
    public int ActiveGraphics => _graphics.Count;

    /// <summary>
    /// Client information for rate limiting and tracking
    /// </summary>
    private sealed record ClientInfo
    {
        public required string ClientId { get; init; } = Guid.NewGuid().ToString();
        public DateTime LastMessageTime { get; set; } = DateTime.UtcNow;
        public Queue<DateTime> MessageTimes { get; init; } = new();
        public int TotalMessages { get; set; }
        public required string RemoteEndPoint { get; init; } = string.Empty;
        public DateTime ConnectedAt { get; init; } = DateTime.UtcNow;
    }

    public SecureOverlayJsonServer(
        OverlayRenderer renderer, 
        ILogger<SecureOverlayJsonServer> logger,
        IConfiguration configuration)
    {
        _renderer = renderer ?? throw new ArgumentNullException(nameof(renderer));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _configuration = configuration ?? throw new ArgumentNullException(nameof(configuration));
        
        // Load configuration with defaults
        _port = _configuration.GetValue("OverlayServer:Port", 5010);
        _maxClients = _configuration.GetValue("OverlayServer:MaxClients", 10);
        _maxMessageSize = _configuration.GetValue("OverlayServer:MaxMessageSize", 10240);
        _rateLimitPerSecond = _configuration.GetValue("OverlayServer:RateLimitPerSecond", 100);
        
        var addressString = _configuration.GetValue("OverlayServer:Address", "127.0.0.1");
        _bindAddress = IPAddress.Parse(addressString);
        
        _allowedCommands = _configuration.GetSection("OverlayServer:AllowedCommands")
            .Get<string[]>()?.ToHashSet(StringComparer.OrdinalIgnoreCase) ?? 
            new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "exit", "clear", "status" };
        
        // Cleanup timer runs every 30 seconds
        _cleanupTimer = new PeriodicTimer(TimeSpan.FromSeconds(30));
        
        _logger.LogInformation("Secure overlay server initialized on {Address}:{Port}", _bindAddress, _port);
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try
        {
            _listener = new TcpListener(_bindAddress, _port);
            _listener.Start();
            
            _logger.LogInformation("Server listening on {Address}:{Port}", _bindAddress, _port);

            // Start cleanup task
            _ = Task.Run(() => CleanupTaskAsync(stoppingToken), stoppingToken);

            // Accept connections
            await AcceptClientsAsync(stoppingToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fatal error in server execution");
            throw;
        }
        finally
        {
            _listener?.Stop();
            await Task.WhenAll(_clientTasks);
            _logger.LogInformation("Server stopped");
        }
    }

    private async Task AcceptClientsAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                var tcpClient = await _listener!.AcceptTcpClientAsync();
                var clientEndpoint = tcpClient.Client.RemoteEndPoint?.ToString() ?? "unknown";
                
                if (_clients.Count >= _maxClients)
                {
                    _logger.LogWarning("Max clients ({MaxClients}) reached, rejecting connection from {Endpoint}", 
                        _maxClients, clientEndpoint);
                    tcpClient.Close();
                    continue;
                }

                var clientInfo = new ClientInfo
                {
                    ClientId = Guid.NewGuid().ToString(),
                    RemoteEndPoint = clientEndpoint
                };
                
                _clients.TryAdd(clientInfo.ClientId, clientInfo);
                
                var clientTask = HandleClientAsync(tcpClient, clientInfo, cancellationToken);
                _clientTasks.Add(clientTask);
                
                _logger.LogInformation("Client connected: {Endpoint} (ID: {ClientId})", 
                    clientEndpoint, clientInfo.ClientId);
            }
            catch (ObjectDisposedException)
            {
                // Server is shutting down
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error accepting client connection");
            }
        }
    }

    private async Task HandleClientAsync(TcpClient client, ClientInfo clientInfo, CancellationToken cancellationToken)
    {
        using (client)
        {
            try
            {
                client.ReceiveTimeout = 30000; // 30 second timeout
                var stream = client.GetStream();
                using var reader = new StreamReader(stream, Encoding.UTF8);

                while (!cancellationToken.IsCancellationRequested && client.Connected)
                {
                    var line = await reader.ReadLineAsync(cancellationToken);
                    if (string.IsNullOrEmpty(line))
                        break;

                    await ProcessMessageAsync(line, clientInfo, cancellationToken);
                }
            }
            catch (OperationCanceledException)
            {
                // Normal shutdown
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error handling client {ClientId}", clientInfo.ClientId);
            }
            finally
            {
                _clients.TryRemove(clientInfo.ClientId, out _);
                _logger.LogInformation("Client disconnected: {Endpoint} (ID: {ClientId}, Duration: {Duration})", 
                    clientInfo.RemoteEndPoint, clientInfo.ClientId, 
                    DateTime.UtcNow - clientInfo.ConnectedAt);
            }
        }
    }

    private async Task ProcessMessageAsync(string jsonMessage, ClientInfo clientInfo, CancellationToken cancellationToken)
    {
        try
        {
            // Rate limiting check
            if (!CheckRateLimit(clientInfo))
            {
                Interlocked.Increment(ref _messageRateLimitedCount);
                _logger.LogWarning("Rate limit exceeded for client {ClientId}", clientInfo.ClientId);
                return;
            }

            // Size validation
            if (jsonMessage.Length > _maxMessageSize)
            {
                Interlocked.Increment(ref _messageErrorCount);
                _logger.LogWarning("Message too large from client {ClientId}: {Size} bytes", 
                    clientInfo.ClientId, jsonMessage.Length);
                return;
            }

            // Parse and validate JSON using System.Text.Json for better performance
            using var document = JsonDocument.Parse(jsonMessage);
            var root = document.RootElement;

            // Security validation
            if (!ValidateMessage(root, clientInfo))
            {
                Interlocked.Increment(ref _messageErrorCount);
                return;
            }

            // Process the message
            await ProcessValidatedMessageAsync(root, clientInfo, cancellationToken);
            
            Interlocked.Increment(ref _messageCount);
            clientInfo.TotalMessages++;
        }
        catch (JsonException ex)
        {
            Interlocked.Increment(ref _messageErrorCount);
            _logger.LogWarning("JSON parsing error from client {ClientId}: {Error}", 
                clientInfo.ClientId, ex.Message);
        }
        catch (Exception ex)
        {
            Interlocked.Increment(ref _messageErrorCount);
            _logger.LogError(ex, "Error processing message from client {ClientId}", clientInfo.ClientId);
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
        
        if (clientInfo.MessageTimes.Count >= _rateLimitPerSecond)
        {
            return false;
        }
        
        clientInfo.MessageTimes.Enqueue(now);
        return true;
    }

    private bool ValidateMessage(JsonElement message, ClientInfo clientInfo)
    {
        try
        {
            // Check for required ID field
            if (!message.TryGetProperty("id", out var idElement) || 
                idElement.ValueKind != JsonValueKind.String)
            {
                _logger.LogWarning("Message missing or invalid 'id' field from client {ClientId}", clientInfo.ClientId);
                return false;
            }

            var id = idElement.GetString();
            if (string.IsNullOrEmpty(id) || !IdPattern().IsMatch(id))
            {
                _logger.LogWarning("Invalid ID format from client {ClientId}: {Id}", clientInfo.ClientId, id);
                return false;
            }

            // Validate text length
            if (message.TryGetProperty("text", out var textElement) && 
                textElement.ValueKind == JsonValueKind.String)
            {
                var text = textElement.GetString();
                var maxLength = _configuration.GetValue("Security:MaxTextLength", 1000);
                if (!string.IsNullOrEmpty(text) && text.Length > maxLength)
                {
                    _logger.LogWarning("Text too long from client {ClientId}: {Length} chars", 
                        clientInfo.ClientId, text.Length);
                    return false;
                }
            }

            // Validate color format
            if (message.TryGetProperty("color", out var colorElement) && 
                colorElement.ValueKind == JsonValueKind.String)
            {
                var color = colorElement.GetString();
                if (!string.IsNullOrEmpty(color) && !ColorPattern().IsMatch(color))
                {
                    _logger.LogWarning("Invalid color format from client {ClientId}: {Color}", 
                        clientInfo.ClientId, color);
                    return false;
                }
            }

            // Validate commands
            if (message.TryGetProperty("command", out var commandElement) && 
                commandElement.ValueKind == JsonValueKind.String)
            {
                var command = commandElement.GetString();
                if (!string.IsNullOrEmpty(command) && !_allowedCommands.Contains(command))
                {
                    _logger.LogWarning("Unauthorized command from client {ClientId}: {Command}", 
                        clientInfo.ClientId, command);
                    return false;
                }
            }

            // Validate numeric ranges
            foreach (var field in new[] { "x", "y", "w", "h", "ttl" })
            {
                if (message.TryGetProperty(field, out var valueElement) && 
                    valueElement.ValueKind == JsonValueKind.Number)
                {
                    var value = valueElement.GetDouble();
                    if (value < -10000 || value > 10000)
                    {
                        _logger.LogWarning("Numeric value out of range from client {ClientId}: {Field}={Value}", 
                            clientInfo.ClientId, field, value);
                        return false;
                    }
                }
            }

            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error validating message from client {ClientId}", clientInfo.ClientId);
            return false;
        }
    }

    private async Task ProcessValidatedMessageAsync(JsonElement message, ClientInfo clientInfo, CancellationToken cancellationToken)
    {
        try
        {
            // Handle special commands
            if (message.TryGetProperty("command", out var commandElement) && 
                commandElement.ValueKind == JsonValueKind.String)
            {
                var command = commandElement.GetString()!;
                await HandleCommandAsync(command, clientInfo, cancellationToken);
                return;
            }

            // Create graphic from message
            var graphic = CreateGraphicFromMessage(message, clientInfo.ClientId);
            if (graphic != null)
            {
                _graphics.AddOrUpdate(graphic.Id, graphic, (key, oldValue) => graphic);
                _logger.LogDebug("Updated graphic '{GraphicId}' from client {ClientId}", 
                    graphic.Id, clientInfo.ClientId);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing validated message from client {ClientId}", clientInfo.ClientId);
        }
    }

    private async Task HandleCommandAsync(string command, ClientInfo clientInfo, CancellationToken cancellationToken)
    {
        switch (command.ToLowerInvariant())
        {
            case "exit":
                _logger.LogInformation("Exit command received from client {ClientId}", clientInfo.ClientId);
                await StopAsync(cancellationToken);
                break;
                
            case "clear":
                _graphics.Clear();
                _logger.LogInformation("Clear command executed by client {ClientId}", clientInfo.ClientId);
                break;
                
            case "status":
                _logger.LogInformation("Status requested by client {ClientId}: " +
                      "Messages: {MessageCount}, Errors: {ErrorCount}, " +
                      "Graphics: {GraphicsCount}, Clients: {ClientCount}",
                      clientInfo.ClientId, MessageCount, MessageErrorCount, 
                      ActiveGraphics, ActiveClients);
                break;
        }
    }

    private static InternalGraphic? CreateGraphicFromMessage(JsonElement message, string clientId)
    {
        try
        {
            if (!message.TryGetProperty("id", out var idElement) || 
                idElement.ValueKind != JsonValueKind.String)
                return null;

            var id = idElement.GetString()!;
            var ttl = 5; // default TTL
            
            if (message.TryGetProperty("ttl", out var ttlElement) && 
                ttlElement.ValueKind == JsonValueKind.Number)
            {
                ttl = ttlElement.GetInt32();
            }

            var graphic = new InternalGraphic
            {
                Id = id,
                ClientId = clientId,
                TTL = ttl,
                CreatedAt = DateTime.UtcNow,
                ExpiresAt = DateTime.UtcNow.AddSeconds(ttl)
            };

            return graphic;
        }
        catch
        {
            return null;
        }
    }

    private async Task CleanupTaskAsync(CancellationToken cancellationToken)
    {
        try
        {
            while (await _cleanupTimer.WaitForNextTickAsync(cancellationToken))
            {
                CleanupExpiredGraphics();
            }
        }
        catch (OperationCanceledException)
        {
            // Normal shutdown
        }
    }

    private void CleanupExpiredGraphics()
    {
        try
        {
            var now = DateTime.UtcNow;
            var expiredKeys = _graphics
                .Where(kvp => kvp.Value.IsExpired(now))
                .Select(kvp => kvp.Key)
                .ToArray(); // Materialize to avoid collection modification issues

            foreach (var key in expiredKeys)
            {
                _graphics.TryRemove(key, out _);
            }

            if (expiredKeys.Length > 0)
            {
                _logger.LogDebug("Cleaned up {Count} expired graphics", expiredKeys.Length);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during graphics cleanup");
        }
    }

    public override void Dispose()
    {
        _cleanupTimer?.Dispose();
        _listener?.Stop();
        base.Dispose();
    }
}