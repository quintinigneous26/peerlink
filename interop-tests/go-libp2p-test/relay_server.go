package main

import (
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/libp2p/go-libp2p"
	"github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/relay"
)

func main() {
	// Create relay host
	host, err := libp2p.New(
		libp2p.ListenAddrStrings("/ip4/0.0.0.0/tcp/9000"),
		libp2p.EnableRelay(),
	)
	if err != nil {
		log.Fatal(err)
	}
	defer host.Close()

	// Start relay service
	_, err = relay.New(host)
	if err != nil {
		log.Fatal(err)
	}

	fmt.Printf("✅ Relay server started\n")
	fmt.Printf("Peer ID: %s\n", host.ID())
	fmt.Printf("Listening on: %v\n", host.Addrs())
	fmt.Println("\nPress Ctrl+C to stop...")

	// Wait for interrupt signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	fmt.Println("\n\n✅ Relay server stopped")
}
