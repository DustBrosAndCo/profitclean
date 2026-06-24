using Microsoft.EntityFrameworkCore;
using DigitalSignage.Shared.Models;

namespace DigitalSignage.CMS.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options)
    {
    }

    public DbSet<Device> Devices { get; set; } = null!;
    public DbSet<ContentItem> ContentItems { get; set; } = null!;
    public DbSet<Playlist> Playlists { get; set; } = null!;

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);
    }
}